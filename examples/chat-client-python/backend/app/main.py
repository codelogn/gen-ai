"""Example chat client — a reference/test consumer of the gen-ai service.

Not a production app: a small, real, working demonstration of the RAG loop
gen-ai is built to serve. Conversations and uploaded-document chunks are
stored ENTIRELY through gen-ai's REST API (see app/genai_client.py) — this
backend's own SQLite database (app/db.py) holds only lightweight
bookkeeping (titles, upload metadata), never chat content or document
content itself.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import db
from app.chat_llm import generate_reply
from app.chunking import chunk_text
from app.config import settings
from app.genai_client import genai_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat-client")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield


app = FastAPI(title="gen-ai example chat client", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class CreateConversationRequest(BaseModel):
    title: str | None = None


class SendMessageRequest(BaseModel):
    content: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/conversations")
async def create_conversation(data: CreateConversationRequest):
    conv_id = await db.create_conversation(data.title)
    return {"id": conv_id}


@app.get("/conversations")
async def list_conversations():
    return await db.list_conversations()


@app.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    conv = await db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await db.get_all_messages(conversation_id)


@app.get("/conversations/{conversation_id}/uploads")
async def get_uploads(conversation_id: str):
    conv = await db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await db.list_uploads(conversation_id)


@app.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, data: SendMessageRequest):
    conv = await db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = data.content.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="content cannot be empty")

    # 1. Persist the user's message — locally (fast, ordered, for UI
    #    rendering + recency window) AND in gen-ai (namespace="messages",
    #    for long-term semantic recall beyond the recency window).
    genai_msg = await genai_client.create_memory(
        namespace=settings.MESSAGES_NAMESPACE,
        content=user_message,
        subject_id=conversation_id,
        metadata={"role": "user"},
    )
    await db.add_message(conversation_id, "user", user_message, genai_msg["id"])
    await db.set_conversation_title_if_unset(conversation_id, user_message)

    # 2. Build context: recency window (local) + semantic search across
    #    both namespaces (gen-ai) — this is the actual RAG loop.
    recent = await db.get_recent_messages(conversation_id, settings.RECENT_MESSAGES_WINDOW)
    message_hits = await genai_client.search(
        namespace=settings.MESSAGES_NAMESPACE,
        query=user_message,
        subject_id=conversation_id,
        top_k=settings.SEMANTIC_SEARCH_TOP_K,
    )
    document_hits = await genai_client.search(
        namespace=settings.DOCUMENTS_NAMESPACE,
        query=user_message,
        subject_id=conversation_id,
        top_k=settings.SEMANTIC_SEARCH_TOP_K,
    )

    system_prompt = _build_system_prompt(recent, message_hits, document_hits)

    # 3. Generate the reply.
    try:
        reply = await generate_reply(system_prompt, user_message)
    except Exception as exc:
        logger.exception("Chat LLM call failed")
        raise HTTPException(status_code=502, detail=f"Chat LLM call failed: {exc}")

    # 4. Persist the assistant's reply the same way as the user's message.
    genai_reply = await genai_client.create_memory(
        namespace=settings.MESSAGES_NAMESPACE,
        content=reply,
        subject_id=conversation_id,
        metadata={"role": "assistant"},
    )
    await db.add_message(conversation_id, "assistant", reply, genai_reply["id"])

    return {"role": "assistant", "content": reply}


@app.post("/conversations/{conversation_id}/upload")
async def upload_document(conversation_id: str, file: UploadFile = File(...)):
    conv = await db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not file.filename.lower().endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only .txt and .md files are supported")

    raw = (await file.read()).decode("utf-8", errors="replace")
    chunks = chunk_text(raw, settings.CHUNK_SIZE_CHARS, settings.CHUNK_OVERLAP_CHARS)
    if not chunks:
        raise HTTPException(status_code=400, detail="File is empty")

    items = [
        {
            "namespace": settings.DOCUMENTS_NAMESPACE,
            "subject_id": conversation_id,
            "content": chunk,
            "metadata": {"filename": file.filename, "chunk_index": i},
        }
        for i, chunk in enumerate(chunks)
    ]
    result = await genai_client.create_memories_batch(items)

    await db.add_upload(conversation_id, file.filename, len(result["created"]))

    return {
        "filename": file.filename,
        "chunks_created": len(result["created"]),
        "chunks_failed": len(result["failed"]),
    }


def _build_system_prompt(recent: list[dict], message_hits: list[dict], document_hits: list[dict]) -> str:
    parts = [
        "You are a helpful assistant in an ongoing conversation. "
        "Use the context below if relevant; otherwise just answer normally."
    ]

    if recent:
        parts.append("\n## Recent conversation")
        for msg in recent:
            parts.append(f"{msg['role']}: {msg['content']}")

    relevant_older = [h for h in message_hits if h["content"] not in {m["content"] for m in recent}]
    if relevant_older:
        parts.append("\n## Relevant earlier messages (found by semantic search)")
        for hit in relevant_older:
            parts.append(f"- {hit['content']} (relevance: {hit['score']:.2f})")

    if document_hits:
        parts.append("\n## Relevant content from uploaded documents")
        for hit in document_hits:
            filename = (hit.get("metadata") or {}).get("filename", "uploaded file")
            parts.append(f"- [{filename}] {hit['content']}")

    return "\n".join(parts)

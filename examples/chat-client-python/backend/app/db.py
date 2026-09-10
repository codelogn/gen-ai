"""Local SQLite — lightweight bookkeeping ONLY.

Conversation titles and upload metadata live here. Chat message content
and document chunk content live in gen-ai (via genai_client.py) — this
database never stores that content, deliberately, to keep it honest that
gen-ai is the system of record for anything RAG-searchable.
"""

import uuid
from pathlib import Path

import aiosqlite

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- Local mirror of message ORDER and ROLE only, for fast recency-window
-- retrieval without a round trip to gen-ai. The message TEXT also lives
-- here for convenience (rendering the chat UI needs it), but gen-ai's copy
-- (namespace="messages") is the one used for semantic recall beyond the
-- recency window and is the copy other consumers/tools would treat as
-- canonical if this example ever needed to be rebuilt from gen-ai alone.
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    genai_memory_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
"""


async def init_db() -> None:
    Path(settings.LOCAL_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def create_conversation(title: str | None = None) -> str:
    conv_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (id, title) VALUES (?, ?)", (conv_id, title)
        )
        await db.commit()
    return conv_id


async def list_conversations() -> list[dict]:
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM conversations ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_conversation(conversation_id: str) -> dict | None:
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_conversation_title_if_unset(conversation_id: str, title: str) -> None:
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET title = ? WHERE id = ? AND (title IS NULL OR title = '')",
            (title[:80], conversation_id),
        )
        await db.commit()


async def add_message(conversation_id: str, role: str, content: str, genai_memory_id: str | None) -> str:
    msg_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, genai_memory_id) VALUES (?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, genai_memory_id),
        )
        await db.commit()
    return msg_id


async def get_recent_messages(conversation_id: str, limit: int) -> list[dict]:
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
            (conversation_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in reversed(rows)]  # chronological order


async def get_all_messages(conversation_id: str) -> list[dict]:
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_upload(conversation_id: str, filename: str, chunk_count: int) -> str:
    upload_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        await db.execute(
            "INSERT INTO uploads (id, conversation_id, filename, chunk_count) VALUES (?, ?, ?, ?)",
            (upload_id, conversation_id, filename, chunk_count),
        )
        await db.commit()
    return upload_id


async def list_uploads(conversation_id: str) -> list[dict]:
    async with aiosqlite.connect(settings.LOCAL_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM uploads WHERE conversation_id = ? ORDER BY created_at DESC",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

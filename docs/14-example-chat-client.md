# The example chat client (Python), walked through

This documents the **Python/FastAPI** implementation specifically. A
second, functionally-equivalent implementation exists in Spring Boot 3 +
Java 21 + React — see
[18-chat-client-java.md](./18-chat-client-java.md) — same RAG loop, same
gen-ai integration, different stack, useful for comparing how the same
integration reads in two languages.

`examples/chat-client-python/` is a small, real, dockerized chat application built
purely to exercise gen-ai's REST API end to end — not a production app, and
not modeled after any specific external system. It's the primary way this
service was validated during development, and it's the reference for
"here's what actually calling gen-ai from a real application looks like."

## What it is

A FastAPI backend (`examples/chat-client-python/backend/`) + a single-file vanilla
HTML/JS frontend (`examples/chat-client-python/frontend/`), each in their own
Docker container. It supports multi-turn conversations and uploading
`.txt`/`.md` documents for retrieval-augmented question answering.

## The architecture decision that makes it a real integration test

The example's own local SQLite database (`app/db.py`) stores **only**
lightweight bookkeeping — conversation titles, upload filenames/chunk
counts. It never stores chat message content or document content. That
content lives **entirely** in gen-ai, via `app/genai_client.py` — a thin
wrapper calling nothing but the public REST contract documented in
[08-api-reference.md](./08-api-reference.md). This is deliberate: if this
example can build a working chat+RAG experience using gen-ai as the actual
system of record for content, that's real evidence the API contract is
sufficient for a real use case — not just internally self-consistent.

(A local copy of message text *is* kept for fast recency-window rendering
— see below — but gen-ai's copy, written on every message, is what the
long-term memory recall depends on, and is the copy any external tool
inspecting this example's data would treat as canonical.)

## The RAG loop, concretely

Every user message triggers, in order (`app/main.py::send_message`):

1. **Persist the message** — both locally (`db.add_message`, for fast
   ordered retrieval) and in gen-ai
   (`genai_client.create_memory(namespace="messages", subject_id=conversation_id, ...)`,
   for long-term semantic recall).
2. **Build context**: the last `RECENT_MESSAGES_WINDOW` (default 6) local
   messages verbatim, **plus** semantic search results from gen-ai across
   both the `"messages"` namespace (older conversation turns beyond the
   recency window) and the `"documents"` namespace (uploaded content) —
   `genai_client.search()`, one call each.
3. **Generate a reply** via a plain chat completion call
   (`app/chat_llm.py` — Ollama or OpenAI, no tool use, no agent loop; this
   is a retrieve-then-generate demonstration, not a tool-calling one).
4. **Persist the reply** the same way as step 1.

## Chunking lives here, not in gen-ai

File upload (`app/main.py::upload_document`) reads the file, splits it with
fixed-size overlapping chunks (`app/chunking.py`, default 500 chars / 50
char overlap), and sends each chunk as a separate memory via
`POST /memories/batch` under namespace `"documents"`. This is the first
genuine need for chunking anywhere in this whole system — gen-ai's own
docs ([03-memory-data-model.md](./03-memory-data-model.md)) note that
messages/short facts don't need it. A document does, and chunking is
correctly the calling application's decision (different consumers may want
different chunk sizes/strategies), not something gen-ai should impose.

## Verified, not just designed

Two acceptance tests were run against the actual running containers
(`docker compose up`, backend reaching gen-ai and a local Ollama instance
via `network_mode: host` — see the example's own
[README.md](../examples/chat-client-python/README.md) for why
`host.docker.internal` doesn't work here):

1. **Document RAG**: a `.txt` file containing a fabricated fact (a
   "Zephyrine Protocol" data-retention policy, invented specifically so the
   answer couldn't come from the model's own training) was uploaded, then
   a question about it was asked. The reply correctly reproduced the
   fabricated details, proving the upload → chunk → embed → search →
   answer path works end to end through the real containers.

2. **Long-term conversation memory**: a fact ("my favorite programming
   language is Rust") was stated, followed by seven unrelated filler
   messages — enough to push it well outside the 6-message recency window.
   A subsequent question ("what programming language did I say I liked
   earlier?") was answered correctly, sourced entirely from gen-ai's
   semantic search over the `"messages"` namespace, not from local
   short-term context. This is the concrete proof that gen-ai's memory
   model — not just its document-search capability — works for a real
   conversational use case.

## What's intentionally out of scope

No PDF parsing (plain text/markdown only — proves the chunking/RAG loop
without an extra parsing dependency). No auth on the example's own
endpoints. No admin-configurable behavior in the example itself (its LLM
provider is a plain environment variable, not a dropdown — that
sophistication belongs to gen-ai, which this is a consumer of, not a
second copy of it).

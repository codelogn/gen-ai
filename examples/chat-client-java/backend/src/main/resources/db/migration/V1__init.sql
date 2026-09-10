-- Local bookkeeping only — NOT the system of record. gen-ai's own
-- /api/v1/memories is canonical for anything semantically searchable;
-- this schema exists purely for fast ordered UI rendering and to know
-- what's been uploaded. Mirrors examples/chat-client-python/backend/app/db.py's
-- SQLite schema, translated to Postgres types (uuid PK, timestamptz).

CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    genai_memory_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);

-- No chunk-content column, same as Python's `uploads` table — chunk text
-- lives only in gen-ai, this is bookkeeping (filename + count) only.
CREATE TABLE uploads (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    filename TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_uploads_conversation_id ON uploads(conversation_id);

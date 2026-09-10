"""Fixed-size chunking with overlap — the first genuine need for chunking
anywhere in this system. gen-ai's own memories/messages don't need it
(see gen-ai's docs/04 — messages are already short, single-turn units);
uploaded documents are the concrete case where content exceeds what's
sensible to embed as one unit, and chunking is correctly an ingestion-side
(client) concern, not something the storage service should impose.
"""


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks

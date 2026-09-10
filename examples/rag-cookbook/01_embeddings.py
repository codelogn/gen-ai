"""Embeddings, hands-on: turn text into a location.

Calls Ollama's embed API directly with plain httpx — no gen-ai dependency
at all. The point of this script isn't gen-ai's API (see docs/13 and the
example chat client for that); it's the underlying RAG concept: what an
embedding model actually returns, and why texts with similar MEANING end
up as nearby vectors even when they share no words.

Prerequisites: a local Ollama running with an embedding model pulled —
`ollama pull nomic-embed-text` if you don't have one yet.

Run: python3 01_embeddings.py
"""

import httpx

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text"

SENTENCES = [
    "The user enjoys cooking pasta",
    "What does the user like to eat?",
    "The user goes hiking on weekends",
]


def embed(text: str) -> list[float]:
    response = httpx.post(OLLAMA_URL, json={"model": MODEL, "prompt": text}, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]


def main():
    print(f"Embedding {len(SENTENCES)} sentences with '{MODEL}'...\n")
    for sentence in SENTENCES:
        vector = embed(sentence)
        preview = ", ".join(f"{x:.4f}" for x in vector[:5])
        print(f"'{sentence}'")
        print(f"  -> {len(vector)} numbers, starts: [{preview}, ...]\n")

    print(
        "Notice: every sentence becomes the SAME number of floats "
        f"({len(embed(SENTENCES[0]))}) regardless of how long the input text was — "
        "that fixed size is the embedding model's 'dimension'. The actual\n"
        "numbers are meaningless on their own; what matters is comparing two\n"
        "vectors to each other, which is exactly what 02_cosine_similarity.py does next."
    )


if __name__ == "__main__":
    main()

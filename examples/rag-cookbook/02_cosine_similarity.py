"""Cosine similarity, hands-on: measuring "how close" two embeddings are.

Computes cosine similarity by hand (plain Python, no numpy) between a
query and several candidate sentences, then reproduces the "Mercurial vs.
Mercury" case documented with real numbers in
docs/05-retrieval-strategies.md and docs/00-rag-concepts-primer.md — a
case where pure vector search gets fooled by two words that are close in
embedding space but mean completely different things.

Prerequisites: same as 01_embeddings.py.

Run: python3 02_cosine_similarity.py
"""

import math

import httpx

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text"


def embed(text: str) -> list[float]:
    response = httpx.post(OLLAMA_URL, json={"model": MODEL, "prompt": text}, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))
    return dot_product / (magnitude_a * magnitude_b)


def ranked_search(query: str, candidates: list[str]) -> list[tuple[str, float]]:
    query_vector = embed(query)
    scored = [(text, cosine_similarity(query_vector, embed(text))) for text in candidates]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)


def main():
    print("=== Part 1: food vs. hiking (the easy case) ===\n")
    results = ranked_search(
        "what does the user like to eat",
        [
            "The user enjoys cooking pasta",
            "The user goes hiking on weekends",
        ],
    )
    for text, score in results:
        print(f"  {score:.4f}  {text}")
    print(
        "\nNotice: 'enjoys cooking pasta' wins even though it shares almost no\n"
        "words with the query — this is what 'searching by meaning' buys you\n"
        "over plain keyword matching.\n"
    )

    print("=== Part 2: Mercurial vs. Mercury (where it breaks) ===\n")
    results = ranked_search(
        "Mercurial",
        [
            "Mercury is the closest planet to the sun and has no atmosphere.",
            "The team switched from Mercurial to Git for managing source code.",
        ],
    )
    for text, score in results:
        print(f"  {score:.4f}  {text}")

    top_result = results[0][0]
    if "planet" in top_result:
        print(
            "\nThis is the real failure mode: the planet Mercury ranks ABOVE the\n"
            "genuinely relevant memory about source control, purely because\n"
            "'Mercurial' and 'Mercury' share a root word and sit close together\n"
            "in embedding space — even though the query has nothing to do with\n"
            "astronomy. See 03_hybrid_search.py for one way to fix this, and\n"
            "docs/05-retrieval-strategies.md for how gen-ai's real hybrid search\n"
            "(BM25 + reciprocal rank fusion) and cross-encoder reranking both\n"
            "address this class of error in production."
        )
    else:
        print(
            "\n(This particular embedding model got it right this time — the\n"
            "failure mode is real and documented with this exact example in\n"
            "docs/05-retrieval-strategies.md, but isn't guaranteed to reproduce\n"
            "identically on every model/run.)"
        )


if __name__ == "__main__":
    main()

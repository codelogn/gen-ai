"""Hybrid search, hands-on: fixing the Mercurial/Mercury failure by hand.

02_cosine_similarity.py showed pure vector search ranking the wrong
answer first for "Mercurial" (embedding similarity gets fooled by the
shared root word with "Mercury"). This script fixes that SAME case with
the simplest possible hybrid: blend cosine similarity with a plain
keyword-overlap score, no library involved.

This is a toy version to make the idea concrete, not what gen-ai actually
runs in production. gen-ai's real `LangChainRetrievalStrategy`
(app/modules/retrieval/langchain_strategy.py) uses a real BM25 ranking
algorithm (term-frequency weighted, not just "count exact word matches")
combined via reciprocal rank fusion, not this hand-rolled blend — see
docs/05-retrieval-strategies.md for the real implementation and its own
worked example with real production numbers.

Prerequisites: same as 01_embeddings.py.

Run: python3 03_hybrid_search.py
"""

import math
import re

import httpx

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text"

QUERY = "Mercurial"
CANDIDATES = [
    "Mercury is the closest planet to the sun and has no atmosphere.",
    "The team switched from Mercurial to Git for managing source code.",
]


def embed(text: str) -> list[float]:
    response = httpx.post(OLLAMA_URL, json={"model": MODEL, "prompt": text}, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))
    return dot_product / (magnitude_a * magnitude_b)


def keyword_overlap_score(query: str, text: str) -> float:
    """The crudest possible keyword score: does the text contain the
    query's exact word, case-insensitively? Real BM25 (what gen-ai
    actually uses) also weighs term frequency and document length — this
    is deliberately simpler, to make the blend easy to follow by hand."""
    query_words = set(re.findall(r"\w+", query.lower()))
    text_words = set(re.findall(r"\w+", text.lower()))
    if not query_words:
        return 0.0
    return len(query_words & text_words) / len(query_words)


def main():
    query_vector = embed(QUERY)
    keyword_weight = 0.5
    vector_weight = 1 - keyword_weight

    print(f"Query: '{QUERY}'  (blend: {keyword_weight:.0%} keyword, {vector_weight:.0%} vector)\n")

    scored = []
    for text in CANDIDATES:
        vector_score = cosine_similarity(query_vector, embed(text))
        keyword_score = keyword_overlap_score(QUERY, text)
        blended = keyword_weight * keyword_score + vector_weight * vector_score
        scored.append((text, vector_score, keyword_score, blended))

    print(f"{'vector-only':>12}  {'keyword':>8}  {'blended':>8}   text")
    for text, vector_score, keyword_score, blended in sorted(scored, key=lambda r: r[3], reverse=True):
        print(f"{vector_score:>12.4f}  {keyword_score:>8.2f}  {blended:>8.4f}   {text}")

    print(
        "\nThe keyword score is 0.0 for the planet sentence (it never uses the\n"
        "literal word 'Mercurial') and 1.0 for the source-control sentence (it\n"
        "does) — that exact-match signal has nothing to do with embedding space,\n"
        "so blending it in corrects the vector-only ranking without needing to\n"
        "change how or where anything is stored. This is the same principle\n"
        "gen-ai's real hybrid strategy and cross-encoder reranking strategy both\n"
        "apply, with more rigorous methods — see docs/05-retrieval-strategies.md."
    )


if __name__ == "__main__":
    main()

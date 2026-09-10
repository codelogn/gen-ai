# RAG cookbook — hands-on, no gen-ai required

Three small, runnable scripts that show the core RAG concepts with real
numbers instead of prose. Read
[../../docs/00-rag-concepts-primer.md](../../docs/00-rag-concepts-primer.md)
alongside these, or after — this cookbook and that doc explain the same
ideas two different ways.

**Deliberately not using gen-ai's own API.** These scripts call Ollama
directly with plain `httpx` and compute everything else by hand (cosine
similarity, keyword overlap) — no gen-ai dependency at all. The goal here
is understanding the underlying RAG concepts themselves, not gen-ai's API
— for that, see [docs/13-adding-a-consuming-application.md](../../docs/13-adding-a-consuming-application.md)
and the [chat-client-python example](../chat-client-python/) (or its
[Java sibling](../chat-client-java/)).

## Prerequisites

- A local [Ollama](https://ollama.com) instance running.
- The `nomic-embed-text` embedding model pulled: `ollama pull nomic-embed-text`
- Python 3 with `httpx` installed (`pip install httpx`) — nothing else.

## Run them in order

```bash
python3 01_embeddings.py       # what an embedding actually looks like
python3 02_cosine_similarity.py  # measuring "how similar" — and where it breaks
python3 03_hybrid_search.py    # fixing the break with a second signal
```

1. **`01_embeddings.py`** — embeds a few plain sentences and prints the
   real vectors (truncated) that come back. The point: text becomes a
   fixed-length list of numbers, and that's it — the interesting part is
   what you can do by *comparing* two of them.
2. **`02_cosine_similarity.py`** — computes cosine similarity by hand
   (no numpy) to rank candidates against a query. Includes the "Mercurial
   vs. Mercury" case: a query for the version-control tool "Mercurial"
   that pure vector search can rank *below* a completely unrelated
   sentence about the *planet* Mercury, because the two words are close
   together in embedding space. This is the exact same case documented
   with production numbers in
   [docs/05-retrieval-strategies.md](../../docs/05-retrieval-strategies.md).
3. **`03_hybrid_search.py`** — fixes that same case with the simplest
   possible hybrid: blend cosine similarity with a plain "does the exact
   word appear" keyword score. This is a toy version to make the idea
   concrete by hand — gen-ai's real `LangChainRetrievalStrategy` uses an
   actual BM25 ranking algorithm combined via reciprocal rank fusion, not
   this simplified blend. See
   [docs/05-retrieval-strategies.md](../../docs/05-retrieval-strategies.md)
   for the real implementation (and gen-ai's cross-encoder reranking
   strategy, which fixes the same class of error a different way).

## What's next

Once these three ideas make sense, [docs/00-rag-concepts-primer.md](../../docs/00-rag-concepts-primer.md)
covers the rest (chunking, vector databases, evaluation) in plain
language, and every doc after it explains how gen-ai itself implements
each piece as a swappable, admin-configurable option.

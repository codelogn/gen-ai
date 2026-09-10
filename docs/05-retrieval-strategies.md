# Retrieval strategies

`RetrievalStrategy` (`app/modules/retrieval/base.py`) answers **how** a
search query becomes ranked results — a separate concern from *where*
vectors are stored (that's `VectorStoreAdapter`, see
[04](./04-vector-store-adapters.md)).

```python
class RetrievalStrategy(ABC):
    async def search(self, db, application, query, top_k, namespace,
                      subject_id=None, filters=None) -> list[SearchResult]: ...
```

No `index()`/write method on this interface — indexing (embed, then
`adapter.upsert()`) is identical regardless of which strategy is active for
both implementations below. A future strategy needing genuinely different
indexing behavior can extend the interface then, not speculatively now.

## `NativeRetrievalStrategy` — the baseline

Embed the query once, call the configured adapter's `query()` directly,
return results ranked by raw cosine similarity. This is every application's
default, and the reference every other strategy is compared against.

## `LangChainRetrievalStrategy` — hybrid keyword + vector search

Wraps the **same** `VectorStoreAdapter` the application is already
configured with — this deliberately does **not** give LangChain its own
storage. A rejected alternative, worth naming explicitly: using LangChain's
own vector-store integrations (`langchain_postgres.PGVector`,
`langchain_qdrant.QdrantVectorStore`) directly would create a second,
divergent copy of the same application's data — breaking the "one source
of truth" property the adapter layer exists to guarantee, and risking the
two copies drifting out of sync on a correction/supersede.

Instead:

1. A small custom `BaseRetriever` subclass (`_StaticDocsRetriever`) wraps
   the adapter's *already-computed* vector search results as LangChain
   `Document` objects — the embedding call happens once, outside, not
   inside the retriever.
2. A `BM25Retriever` (keyword/TF-IDF ranking) is built fresh per search
   call from the application's active `memories.content` for the requested
   namespace — fine at the scale this is designed for; would need
   revisiting if a namespace's active-memory count grows into the tens of
   thousands (rebuilding a BM25 index over that many docs on every call
   would become the bottleneck).
3. `EnsembleRetriever` combines both via reciprocal rank fusion, weighted
   by `retrieval_strategy_config.hybrid_keyword_weight` (default 0.3 —
   30% keyword, 70% vector).

No LLM call anywhere in this strategy — it's pure ranking-algorithm
composition (query rewriting via an LLM is explicitly deferred, see the
non-goals in the original design plan).

### Why hybrid, demonstrated not just asserted

Pure vector search can be fooled by lexical similarity that has nothing to
do with actual relevance. Verified directly during development: with
memories about "Mercurial" (version control) and "Mercury" (the planet)
both present, a query for "Mercurial" under `native` ranked the
Mercury-planet memory *above* a genuinely relevant memory about managing
source code — because "Mercurial" and "Mercury" are close in embedding
space, while "manages source code" shares no surface tokens with either.
BM25's exact-term matching, blended in via `langchain`, corrects exactly
this class of error without needing any change to how or where the data is
stored.

A second, cleaner demonstration: a memory containing the rare literal name
"Bartholomew" was queried directly. Under `native`, its score was a
middling cosine similarity (0.62) alongside two competing, topically
similar memories about puppies. Under `langchain`, BM25's exact match
pushed it to the top with a full weight (rank-based score 1.0), with the
same ranking order preserved for the rest.

### On the score field

`EnsembleRetriever`'s reciprocal-rank-fusion merge doesn't produce one
comparable similarity number the way native cosine search does — a merged
document's rank reflects *both* retrievers' opinions, not one metric. So
`LangChainRetrievalStrategy` scores results by rank position
(`1 / (rank + 1)`) rather than trying to recover or trust whatever raw
metadata survives the ensemble's internal merge. Don't compare a
`langchain`-strategy score against a `native`-strategy score as if they
were the same unit — they answer different questions ("how does this rank
relative to the others" vs. "how similar is this to the query").

## `CrossEncoderRerankStrategy` — cross-encoder reranking

Fetches a wider candidate pool from the configured `VectorStoreAdapter`
(`retrieval_strategy_config.rerank_candidate_pool`, default
`max(top_k × 4, 20)`, hard-capped at 100 regardless of config — an
unbounded pool is a real latency/CPU vector in a shared multi-tenant
process) via the same logic `NativeRetrievalStrategy` uses, then re-scores
every (query, candidate) pair with a **cross-encoder** — a model that
reads the query and candidate *together* as one input, rather than
comparing two independently-computed embedding vectors the way cosine
similarity does. This lets it catch relevance signals cosine similarity
structurally can't see: reading both texts jointly means it can recognize
true relevance despite low lexical/embedding overlap, and reject false
positives despite high lexical/embedding overlap.

This is the first strategy — and the first feature in this whole
service — that runs actual local ML inference (via
`sentence-transformers`/`torch`) rather than calling an HTTP API. That
distinction drives real engineering constraints documented in
`app/modules/retrieval/reranked_strategy.py`'s module docstring:
cross-encoder inference is synchronous, CPU-bound code, so it's offloaded
to a dedicated thread pool (not run inline in `async def search()`,
which would block the event loop for every other concurrent request);
the model is cached in-process by name with a negative-cache TTL on load
failures; and `rerank_model` is restricted to a small allowlist rather
than accepted as an arbitrary string, since an arbitrary HF model name
from any tenant's config becomes something this shared process downloads
and holds in memory indefinitely.

**Fails soft, not hard.** If the model can't be loaded or scoring fails
for any reason, `search()` logs a warning and returns the candidates in
plain vector-score order — i.e., exactly `NativeRetrievalStrategy`'s
result — rather than erroring the request. Verified directly: pointing
`rerank_model` at an unrecognized name produced a logged warning and a
normal `200` response with correctly (default-model) reranked results,
not a failure.

### Why reranking, demonstrated not just asserted

Reusing the exact "Mercurial vs. Mercury" adversarial case documented
above for hybrid search: with both memories present, querying "Mercurial"
under `native` reproduced the same known misranking —

| Strategy | "Mercury is the closest planet..." | "...switched from Mercurial to Git..." |
|---|---|---|
| `native` (cosine) | **0.588** (ranked #1 — wrong) | 0.534 (ranked #2) |
| `reranked` (cross-encoder) | -11.41 (ranked #2 — correct) | **2.99** (ranked #1 — correct) |

The cross-encoder doesn't just nudge the score, it inverts the ranking
with a huge margin, because it reads "Mercurial" and "Mercury is the
closest planet to the sun" *together* and recognizes they share no actual
relevance despite sitting close together in embedding space — the same
class of error BM25 fixes via exact-term matching, but arrived at through
reading comprehension instead of lexical matching. (Cross-encoder scores
are raw, unbounded model logits, not a 0-1 similarity — don't compare them
against a `native` cosine score or a `langchain` rank-based score as if
they were the same unit, same caveat as the score-field note above.)

**Not a universal upgrade, though — verified honestly, not just the win
case.** A separate test case (a paraphrased answer — "Bartholomew is what
they call their new golden retriever" — answering "what is the current
name of the user's puppy") was *not* fixed by reranking: the cross-encoder
ranked a clearly-irrelevant distractor ("the user's childhood dog... passed
away five years ago") even higher than `native` did, and ranked the
correct paraphrase lowest of all five candidates. `ms-marco-MiniLM-L-6-v2`
is trained for passage-relevance ranking, not for recognizing that "golden
retriever" satisfies a question about "puppy" without more shared context.
Reranking is a real, measurable improvement for the class of error it's
good at (lexical-similarity false positives, the Mercurial/Mercury shape)
and not a fix for every ranking problem — pick it deliberately, not as a
default "always better" upgrade over `native`.

## Extensibility

`get_strategy(application)` (`app/modules/retrieval/factory.py`) mirrors
the adapter factory's shape exactly. See
[12-adding-a-retrieval-strategy.md](./12-adding-a-retrieval-strategy.md)
for the recipe to add a fourth.

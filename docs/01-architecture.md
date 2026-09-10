# Architecture

## Request flow

```
Consumer app ──X-API-Key──► POST /api/v1/memories/search
                                  │
                                  ▼
                         get_current_application()   [app/core/deps.py]
                         verifies the key (hashed compare), resolves Application row
                                  │
                                  ▼
                         enforce_rate_limit()         [app/core/rate_limit.py]
                         per-application sliding window, 429 if exceeded
                                  │
                                  ▼
                         get_strategy(application)    [app/modules/retrieval/factory.py]
                         picks NativeRetrievalStrategy or LangChainRetrievalStrategy
                                  │
                                  ├─► EmbeddingProviderRegistry.embed(query)   [Ollama or OpenAI]
                                  │
                                  ├─► get_adapter(application).query(vector, filters={namespace, subject_id})
                                  │       [SqliteVecAdapter | PgvectorAdapter | QdrantAdapter]
                                  │
                                  └─► look up matched memory_ids in Postgres `memories`
                                         (the system of record for content/metadata — always,
                                         regardless of which vector backend served the search)
                                  │
                                  ▼
                         SearchResult list ──► JSON response

Meanwhile, RequestLoggingMiddleware wraps the whole request, writing one
durable RequestLog row (application, path, status, latency, which
strategy/backend actually served it) — see 09-observability-and-troubleshooting.md.
```

Writes (`POST /api/v1/memories`) follow the same shape minus the strategy
layer: embed once via `EmbeddingProviderRegistry`, `INSERT` into `memories`
(Postgres), then `adapter.upsert()` the vector into whichever backend is
configured.

## The two independently-swappable axes

This service has exactly two seams, and they don't know about each other:

1. **Storage** (`VectorStoreAdapter`, `app/modules/vectorstore/`) — answers
   "where is the vector, and how do I get it back by similarity." Three
   implementations: `SqliteVecAdapter` (a local file, no server),
   `PgvectorAdapter` (a table in the same control-plane Postgres),
   `QdrantAdapter` (a dedicated vector database server). See
   [04-vector-store-adapters.md](./04-vector-store-adapters.md).

2. **Retrieval** (`RetrievalStrategy`, `app/modules/retrieval/`) — answers
   "how does a query become ranked results." Two implementations:
   `NativeRetrievalStrategy` (embed + call the adapter directly),
   `LangChainRetrievalStrategy` (the same adapter, wrapped as a LangChain
   retriever, combined with BM25 keyword search via `EnsembleRetriever`).
   See [05-retrieval-strategies.md](./05-retrieval-strategies.md).

A consumer never sees either choice — `POST /memories/search`'s request/
response shape is identical no matter which of the 3×2 combinations an
admin has configured for that application. This was verified directly
during development: the same query against the same data, run through all
three storage backends, produced matching cosine scores to four decimal
places; switching retrieval strategy on a live application changed ranking
behavior without touching stored data at all.

## Why this is the first shared-backend pattern here, and what that changes

Every other application on this host is a self-contained monolith with its
own database and its own users. This service inverts that: multiple
independent consumers now have a hard runtime dependency on one process.
Concretely, this shaped three decisions documented elsewhere in this set:

- The admin panel's "Logs & usage" tab
  ([09-observability-and-troubleshooting.md](./09-observability-and-troubleshooting.md))
  isn't a nice-to-have — it's the only tool anyone has for "why did my
  search just fail," since a consumer has no visibility into this
  service's internals.
- Every interface (`VectorStoreAdapter`, `RetrievalStrategy`) is a real,
  enforced Python ABC, not an internal convenience — the whole point of
  building this as a service is that storage and retrieval choices need to
  swap without touching what depends on them.
- `/health` (liveness) and `/ready` (can this instance actually serve —
  checks DB connectivity) are deliberately separate endpoints, a
  distinction that matters once other systems' orchestration depends on
  this one being up.

## Directory layout

```
backend/app/
  main.py                    # app assembly, middleware, /health, /ready
  core/                      # config, DB session, auth (both realms), rate limiting, idempotency
  api/v1/endpoints/          # thin route handlers — consumer (memories.py) and admin (admin_*.py)
  modules/
    applications/            # the Application tenant model — the three dropdown choices live here
    admin_auth/               # AdminUser — independent human login realm
    api_keys/                 # ApplicationApiKey — hashed service-to-service credentials
    memory/                   # the generic Memory model + write-path service
    embeddings/               # EmbeddingProviderRegistry (Ollama/OpenAI)
    vectorstore/               # VectorStoreAdapter + 3 implementations + factory
    retrieval/                 # RetrievalStrategy + 3 implementations + factory
    evaluation/                # EvaluationFramework fan-out (native/ragas/deepeval)
    usage/                     # RequestLog, IdempotencyKey, the logging middleware
  admin_ui/                   # Jinja2 templates + routes — the browser-facing admin panel
examples/chat-client-python/  # dockerized reference consumer, FastAPI+vanilla JS (14-example-chat-client.md)
examples/chat-client-java/    # same reference consumer, Spring Boot 3+React (18-chat-client-java.md)
examples/rag-cookbook/        # standalone, no-gen-ai-dependency RAG concept walkthroughs
```

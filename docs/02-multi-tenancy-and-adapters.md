# Multi-tenancy & the adapter pattern

## The `Application` model — a first-class tenant

Every registered consumer of this service is one row in `applications`
(`app/modules/applications/models.py`). A consuming system doesn't
authenticate as a user — it authenticates as an **application**, and every
piece of data it writes is scoped by `application_id`.

Fields worth understanding beyond the obvious `slug`/`display_name`:

| Field | Purpose |
|---|---|
| `vector_backend` | one of `sqlite_vec` / `pgvector` / `qdrant` — dropdown #1 |
| `vector_backend_generation` | bumped every time the backend or embedding model changes; see [04](./04-vector-store-adapters.md) |
| `retrieval_strategy` | one of `native` / `langchain` — dropdown #2 |
| `retrieval_strategy_config` | JSON, strategy-specific (e.g. `hybrid_keyword_weight` for `langchain`) |
| `embedding_provider` / `embedding_model` | dropdown #3 + the model name |
| `embedding_dimension` | **auto-detected**, not admin-typed — set on the application's first write, by actually calling the embedding provider once and measuring the vector length |
| `rate_limit_per_minute` | nullable — falls back to a global default |

Three admin-facing dropdowns, three independent interfaces behind them
(§ below), zero hardcoded per-consumer logic anywhere in the codebase.

## Why "adapter" (a.k.a. the port/adapter pattern)

Both `VectorStoreAdapter` and `RetrievalStrategy` follow the same shape:
an abstract Python class (`abc.ABC`) defining the *contract* a caller
depends on, with concrete implementations behind a factory function
(`get_adapter(application)`, `get_strategy(application)`) that the caller
never has to know about.

```python
# app/modules/vectorstore/base.py
class VectorStoreAdapter(ABC):
    async def provision(self, application, dimension) -> None: ...
    async def upsert(self, application, memory_id, vector, payload) -> None: ...
    async def query(self, application, vector, top_k, filters=None) -> list[VectorMatch]: ...
    async def mark_inactive(self, application, memory_id) -> None: ...
    async def delete(self, application, memory_id) -> None: ...
    async def health_check(self, application) -> bool: ...
```

Every caller in this codebase (`MemoryService`, `NativeRetrievalStrategy`,
`LangChainRetrievalStrategy`) only ever calls these six methods — never a
backend-specific detail. This is what makes "an admin picks a different
backend from a dropdown" a real, safe operation instead of a
find-and-replace across the codebase: the factory function is the *only*
place that branches on which backend is configured.

```python
# app/modules/vectorstore/factory.py
def get_adapter(application: Application) -> VectorStoreAdapter:
    if application.vector_backend == VectorBackend.SQLITE_VEC:
        return _sqlite_vec_adapter
    elif application.vector_backend == VectorBackend.PGVECTOR:
        from app.modules.vectorstore.pgvector_adapter import get_pgvector_adapter
        return get_pgvector_adapter()
    elif application.vector_backend == VectorBackend.QDRANT:
        from app.modules.vectorstore.qdrant_adapter import get_qdrant_adapter
        return get_qdrant_adapter()
    else:
        raise ValueError(f"Unsupported vector backend: {application.vector_backend}")
```

The same shape, `get_strategy(application)`, exists in
`app/modules/retrieval/factory.py` for retrieval strategies.

## Two adapters, not one

It would be simpler to have one interface serve one purpose. This service
deliberately has **two**, because "where data is stored" and "how a search
ranks results" are genuinely different concerns that don't need to change
together:

- Switching `vector_backend` from `sqlite_vec` to `qdrant` changes nothing
  about how ranking works — both `NativeRetrievalStrategy` and
  `LangChainRetrievalStrategy` call the exact same `adapter.query()` method
  regardless of which adapter it resolves to.
- Switching `retrieval_strategy` from `native` to `langchain` changes
  nothing about where data lives — `LangChainRetrievalStrategy` calls the
  *same* `VectorStoreAdapter` the application is already configured with;
  it does not give LangChain its own storage (see
  [05-retrieval-strategies.md](./05-retrieval-strategies.md) for why that
  alternative was rejected).

This was proven, not just designed: during development, an application was
switched from `sqlite_vec` to `pgvector` mid-testing and continued serving
identical search behavior once data was re-upserted; a separate
application was switched from `native` to `langchain` with zero change to
its stored vectors, and the *same* stored data produced different
(correctly different — hybrid keyword+vector) rankings immediately.

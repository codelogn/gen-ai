# Recipe: adding a fourth retrieval strategy

Say you want to add, e.g., a LlamaIndex-based strategy, or an LLM-based
reranking pass (a *cross-encoder* reranking pass now exists for real —
`CrossEncoderRerankStrategy`, see
[05-retrieval-strategies.md](./05-retrieval-strategies.md) — read it
first for a worked example of the tradeoffs a reranking-style strategy
runs into, including the honest case where it *doesn't* help). Steps:

## 1. Implement `RetrievalStrategy`

New file `app/modules/retrieval/your_strategy.py`:

```python
from app.modules.retrieval.base import RetrievalStrategy, SearchResult

class YourStrategy(RetrievalStrategy):
    async def search(self, db, application, query, top_k, namespace,
                      subject_id=None, filters=None) -> list[SearchResult]:
        # You still call the SAME VectorStoreAdapter the application is
        # configured with — do not give your strategy its own storage.
        # See docs/05-retrieval-strategies.md for why that's a rejected
        # pattern (it breaks "one source of truth" for an application's data).
        from app.modules.vectorstore.factory import get_adapter
        from app.modules.embeddings.registry import EmbeddingProviderRegistry

        vectors = await EmbeddingProviderRegistry.embed(application, [query])
        adapter = get_adapter(application)
        matches = await adapter.query(
            application, vectors[0], top_k=top_k,
            filters={"namespace": namespace, "subject_id": subject_id},
        )
        # ... your ranking/reranking logic here ...
        # then look up content from Postgres `memories` (always the system
        # of record — see docs/03-memory-data-model.md) for whatever
        # memory_ids you end up returning.
        ...

_your_strategy = YourStrategy()

def get_your_strategy() -> YourStrategy:
    return _your_strategy
```

## 2. Add the enum value

`app/modules/applications/models.py`:

```python
class RetrievalStrategyName(str, enum.Enum):
    NATIVE = "native"
    LANGCHAIN = "langchain"
    YOUR_STRATEGY = "your_strategy"  # add this
```

## 3. Register in the factory

`app/modules/retrieval/factory.py`:

```python
elif application.retrieval_strategy == RetrievalStrategyName.YOUR_STRATEGY:
    from app.modules.retrieval.your_strategy import get_your_strategy
    return get_your_strategy()
```

## 4. Add config fields if needed, and the admin UI dropdown option

If your strategy needs tunables (like `langchain`'s
`hybrid_keyword_weight`), read them from
`application.retrieval_strategy_config` (a free-form JSON dict) and add a
conditionally-shown form field in
`app/admin_ui/templates/application_form.html`, following the existing
`langchain-fields` pattern (a `<div>` toggled by the strategy `<select>`'s
`onchange` handler).

## 5. Verify

The acceptance bar used for `LangChainRetrievalStrategy`: on the *same*
application/data, run an identical search query under the existing default
(`native`) and under your new strategy, and confirm the ranked results
**genuinely differ** in a way you can explain — not just a different score
scale, an actual different ranking driven by your strategy's specific
logic. If the results are identical, either your strategy isn't adding
anything over native search, or there's a bug in the wiring.

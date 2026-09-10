"""get_strategy(application) -> RetrievalStrategy

Mirrors vectorstore/factory.py's shape. Adding a third strategy later means
implementing the one-method RetrievalStrategy interface and adding an enum
value + admin dropdown option — see docs/12-adding-a-retrieval-strategy.md.
"""

from app.modules.applications.models import Application, RetrievalStrategyName
from app.modules.retrieval.base import RetrievalStrategy
from app.modules.retrieval.native_strategy import NativeRetrievalStrategy

_native_strategy = NativeRetrievalStrategy()


def get_strategy(application: Application) -> RetrievalStrategy:
    if application.retrieval_strategy == RetrievalStrategyName.NATIVE:
        return _native_strategy
    elif application.retrieval_strategy == RetrievalStrategyName.LANGCHAIN:
        from app.modules.retrieval.langchain_strategy import get_langchain_strategy

        return get_langchain_strategy()
    elif application.retrieval_strategy == RetrievalStrategyName.RERANKED:
        from app.modules.retrieval.reranked_strategy import get_reranked_strategy

        return get_reranked_strategy()
    else:
        raise ValueError(f"Unsupported retrieval strategy: {application.retrieval_strategy}")

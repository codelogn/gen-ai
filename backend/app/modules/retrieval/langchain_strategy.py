"""LangChainRetrievalStrategy — hybrid keyword + vector search.

Wraps the SAME VectorStoreAdapter and embedding config as a LangChain-
compatible retriever — this deliberately does NOT give LangChain its own
separate storage (a rejected alternative: using LangChain's own vector-store
integrations directly would create a second, divergent copy of the same
application's data, breaking the "one source of truth" property the
adapter layer exists to guarantee).

Instead: a small custom BaseRetriever wraps our own precomputed vector
search results, combined with a BM25Retriever (keyword/TF-IDF-style
ranking) built fresh per search from the application's active memories.content
for that namespace, via an EnsembleRetriever. No LLM call — pure
ranking-algorithm composition, not query rewriting (see docs/05-retrieval-strategies.md).
"""

from typing import Any, Optional

# EnsembleRetriever moved to langchain_classic in LangChain's 1.x
# restructuring (was langchain.retrievers pre-1.0) — caught and fixed
# during the evaluation-frameworks dependency upgrade, which forced
# langchain-core/-community onto the 1.x line.
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.callbacks import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.embeddings.registry import EmbeddingProviderRegistry
from app.modules.memory.models import Memory, MemoryStatus
from app.modules.retrieval.base import RetrievalStrategy, SearchResult
from app.modules.vectorstore.factory import get_adapter

DEFAULT_HYBRID_KEYWORD_WEIGHT = 0.3


class _StaticDocsRetriever(BaseRetriever):
    """A trivial LangChain retriever that returns a precomputed list of
    Documents. Used to make our own vector search results composable with
    EnsembleRetriever without needing the retriever itself to do async
    embedding calls internally — the embedding call already happened once,
    outside, in LangChainRetrievalStrategy.search()."""

    docs: list[Document] = []

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        return self.docs

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: AsyncCallbackManagerForRetrieverRun
    ) -> list[Document]:
        return self.docs


class LangChainRetrievalStrategy(RetrievalStrategy):
    async def search(
        self,
        db: AsyncSession,
        application: Application,
        query: str,
        top_k: int,
        namespace: str,
        subject_id: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        # Load the full active corpus for this (application, namespace,
        # subject_id) — BM25 needs the whole corpus text to rank against,
        # and reusing this same set avoids a second DB round trip for the
        # vector side below. Fine at the scale this strategy is designed
        # for (see docs/05-retrieval-strategies.md); would need revisiting
        # if a namespace's active-memory count grows into the tens of
        # thousands (rebuilding a BM25 index over that many docs on every
        # search call would become the bottleneck).
        conditions = [
            Memory.application_id == application.id,
            Memory.namespace == namespace,
            Memory.status == MemoryStatus.ACTIVE,
        ]
        if subject_id:
            conditions.append(Memory.subject_id == subject_id)
        result = await db.execute(select(Memory).where(*conditions))
        memories = list(result.scalars().all())

        if not memories:
            return []

        memories_by_id = {str(m.id): m for m in memories}

        # --- BM25 (keyword) retriever ---
        bm25_retriever = BM25Retriever.from_texts(
            texts=[m.content for m in memories],
            ids=[str(m.id) for m in memories],
            k=top_k,
        )

        # --- Vector retriever (precomputed, wrapped for Ensemble compatibility) ---
        query_vectors = await EmbeddingProviderRegistry.embed(application, [query])
        adapter = get_adapter(application)
        adapter_filters = {"namespace": namespace, "subject_id": subject_id}
        vector_matches = await adapter.query(
            application, query_vectors[0], top_k=top_k, filters=adapter_filters
        )
        vector_docs = [
            Document(
                id=str(match.memory_id),
                page_content=memories_by_id[str(match.memory_id)].content,
                metadata={"vector_score": match.score},
            )
            for match in vector_matches
            if str(match.memory_id) in memories_by_id
        ]
        vector_retriever = _StaticDocsRetriever(docs=vector_docs)

        # --- Combine ---
        config = application.retrieval_strategy_config or {}
        keyword_weight = float(config.get("hybrid_keyword_weight", DEFAULT_HYBRID_KEYWORD_WEIGHT))
        keyword_weight = min(max(keyword_weight, 0.0), 1.0)
        vector_weight = 1.0 - keyword_weight

        ensemble = EnsembleRetriever(
            retrievers=[vector_retriever, bm25_retriever],
            weights=[vector_weight, keyword_weight],
        )
        merged_docs = await ensemble.ainvoke(query)

        # The ensemble's reciprocal-rank-fusion merge doesn't produce a
        # single comparable similarity number the way native cosine search
        # does — a merged doc's rank reflects BOTH retrievers' opinions,
        # not one metric. Score by rank position instead of trying to
        # recover/trust whatever raw metadata survived the merge.
        results: list[SearchResult] = []
        for rank, doc in enumerate(merged_docs[:top_k]):
            memory = memories_by_id.get(doc.id)
            if memory is None:
                continue
            results.append(
                SearchResult(
                    memory_id=memory.id,
                    content=memory.content,
                    metadata=memory.metadata_,
                    score=round(1.0 / (rank + 1), 4),
                    created_at=memory.created_at.isoformat(),
                )
            )
        return results


_langchain_strategy = LangChainRetrievalStrategy()


def get_langchain_strategy() -> LangChainRetrievalStrategy:
    return _langchain_strategy

"""NativeRetrievalStrategy — the straightforward baseline.

Embed the query, call the configured VectorStoreAdapter directly, return
results ranked by raw similarity. Default for every application, and the
reference every other strategy is compared against. See
docs/05-retrieval-strategies.md.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.embeddings.registry import EmbeddingProviderRegistry
from app.modules.memory.models import Memory, MemoryStatus
from app.modules.retrieval.base import RetrievalStrategy, SearchResult
from app.modules.vectorstore.factory import get_adapter


class NativeRetrievalStrategy(RetrievalStrategy):
    async def search(
        self,
        db: AsyncSession,
        application: Application,
        query: str,
        top_k: int,
        namespace: str,
        subject_id: Optional[str] = None,
        filters: Optional[dict] = None,
    ) -> list[SearchResult]:
        vectors = await EmbeddingProviderRegistry.embed(application, [query])
        query_vector = vectors[0]

        # namespace is a required filter, not optional — see
        # VectorStoreAdapter.query()'s docstring on why an unscoped KNN
        # search across an application's whole vector space is incorrect.
        adapter_filters = {"namespace": namespace, "subject_id": subject_id, **(filters or {})}
        adapter = get_adapter(application)
        matches = await adapter.query(application, query_vector, top_k=top_k, filters=adapter_filters)
        if not matches:
            return []

        memory_ids = [m.memory_id for m in matches]
        result = await db.execute(
            select(Memory).where(
                Memory.id.in_(memory_ids),
                Memory.application_id == application.id,
                Memory.namespace == namespace,
                Memory.status == MemoryStatus.ACTIVE,
                *([Memory.subject_id == subject_id] if subject_id else []),
            )
        )
        memories_by_id = {m.id: m for m in result.scalars().all()}

        results: list[SearchResult] = []
        for match in matches:
            memory = memories_by_id.get(match.memory_id)
            if memory is None:
                # Vector store had a stale/inactive/wrong-namespace entry —
                # skip rather than surface a result with no backing content.
                continue
            results.append(
                SearchResult(
                    memory_id=memory.id,
                    content=memory.content,
                    metadata=memory.metadata_,
                    score=match.score,
                    created_at=memory.created_at.isoformat(),
                )
            )
        return results

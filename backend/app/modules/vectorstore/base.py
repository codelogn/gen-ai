"""The storage contract every vector backend implements.

Answers only "where is the vector stored and how do I get it back by ID or
by raw similarity" — nothing about ranking strategy, hybrid search, or
query rewriting lives here. See app/modules/retrieval/base.py for that
layer, and docs/04-vector-store-adapters.md / docs/05-retrieval-strategies.md
for the full design rationale behind keeping these two concerns separate.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

from app.modules.applications.models import Application


class VectorMatch(BaseModel):
    memory_id: uuid.UUID
    score: float


class VectorStoreAdapter(ABC):
    @abstractmethod
    async def provision(self, application: Application, dimension: int) -> None:
        """Create the per-application store for this backend+generation.
        Idempotent — calling it again for an already-provisioned
        (application, generation) pair is a no-op."""
        raise NotImplementedError

    @abstractmethod
    async def upsert(
        self,
        application: Application,
        memory_id: uuid.UUID,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def query(
        self,
        application: Application,
        vector: list[float],
        top_k: int,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[VectorMatch]:
        """filters is an equality-match dict applied BEFORE ranking/limiting
        to top_k — every implementation must at minimum support "namespace"
        and "subject_id" keys, since a single application's vector space
        holds every namespace's vectors together and a KNN search with no
        namespace filter can otherwise return fewer than top_k valid
        results (or the wrong ones) whenever another namespace's content
        happens to be nearby in embedding space. This is not optional
        filtering for convenience — it's required for correctness."""
        raise NotImplementedError

    @abstractmethod
    async def mark_inactive(self, application: Application, memory_id: uuid.UUID) -> None:
        """Called on supersede/soft-delete. May be a no-op if the backend's
        query() already filters status by joining back to the memories
        table (e.g. pgvector); for a backend that carries its own payload
        (e.g. Qdrant), this should update that payload so the backend's own
        filtering excludes it without a round trip."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, application: Application, memory_id: uuid.UUID) -> None:
        """Hard delete from the vector index."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self, application: Application) -> bool:
        raise NotImplementedError

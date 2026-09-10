"""The retrieval-strategy contract — the file that makes "swap the AI
design" a real, enforced interface rather than a scattered set of if/else
branches. See docs/05-retrieval-strategies.md.

A RetrievalStrategy decides HOW a search query gets turned into ranked
results — it composes an embedding provider and a vector-store adapter,
but owns the actual retrieval logic. Deliberately no index()/write method
here: indexing is identical regardless of active strategy for the two V1
implementations (native, langchain) — see the module docstring in
native_strategy.py for what would justify adding one later.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application


class SearchResult(BaseModel):
    memory_id: uuid.UUID
    content: str
    metadata: Optional[dict] = None
    score: float
    created_at: str


class RetrievalStrategy(ABC):
    @abstractmethod
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
        """db is needed because Postgres (the memories table) is always the
        system of record for content/metadata, regardless of which vector
        backend or strategy is active — see docs/03-memory-data-model.md."""
        raise NotImplementedError

"""MemoryService — write path (embed + store) and lifecycle operations
(supersede, delete) for the generic memories table. Search/read path lives
in the active RetrievalStrategy (app/modules/retrieval/), not here — this
service owns writes and the plain "system of record" reads (get by id).
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.embeddings.registry import EmbeddingProviderRegistry
from app.modules.memory.models import Memory, MemoryStatus
from app.modules.vectorstore.factory import get_adapter


class MemoryService:
    async def _ensure_provisioned(self, application: Application) -> int:
        """Ensure the vector backend is provisioned for this application's
        current generation, auto-detecting dimension on first use if it
        hasn't been detected yet. Returns the dimension."""
        if application.embedding_dimension is None:
            application.embedding_dimension = await EmbeddingProviderRegistry.detect_dimension(
                application
            )
            adapter = get_adapter(application)
            await adapter.provision(application, application.embedding_dimension)
        return application.embedding_dimension

    async def create(
        self,
        db: AsyncSession,
        application: Application,
        namespace: str,
        content: str,
        subject_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        source_ref: Optional[str] = None,
    ) -> Memory:
        dimension = await self._ensure_provisioned(application)

        memory = Memory(
            application_id=application.id,
            namespace=namespace,
            subject_id=subject_id,
            content=content,
            metadata_=metadata,
            source_ref=source_ref,
            status=MemoryStatus.ACTIVE,
            vector_backend_generation=application.vector_backend_generation,
        )
        db.add(memory)
        await db.flush()  # get memory.id before embedding/upserting the vector

        vectors = await EmbeddingProviderRegistry.embed(application, [content])
        adapter = get_adapter(application)
        await adapter.upsert(
            application,
            memory.id,
            vectors[0],
            payload={
                "application_id": str(application.id),
                "namespace": namespace,
                "subject_id": subject_id,
                "status": MemoryStatus.ACTIVE.value,
            },
        )

        await db.commit()
        await db.refresh(memory)
        # embedding_dimension may have just been set on `application` above —
        # persist that too, if it changed.
        if db.is_modified(application):
            await db.commit()
        return memory

    async def get(
        self, db: AsyncSession, application_id: uuid.UUID, memory_id: uuid.UUID
    ) -> Optional[Memory]:
        result = await db.execute(
            select(Memory).where(Memory.id == memory_id, Memory.application_id == application_id)
        )
        return result.scalar_one_or_none()

    async def supersede(
        self,
        db: AsyncSession,
        application: Application,
        memory_id: uuid.UUID,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Optional[Memory]:
        old_memory = await self.get(db, application.id, memory_id)
        if old_memory is None:
            return None

        new_memory = await self.create(
            db,
            application,
            namespace=old_memory.namespace,
            content=content,
            subject_id=old_memory.subject_id,
            metadata=metadata if metadata is not None else old_memory.metadata_,
            source_ref=old_memory.source_ref,
        )

        old_memory.status = MemoryStatus.SUPERSEDED
        old_memory.superseded_by_id = new_memory.id
        await db.commit()

        adapter = get_adapter(application)
        await adapter.mark_inactive(application, old_memory.id)

        await db.refresh(new_memory)
        return new_memory

    async def delete(
        self, db: AsyncSession, application: Application, memory_id: uuid.UUID, hard: bool = False
    ) -> bool:
        memory = await self.get(db, application.id, memory_id)
        if memory is None:
            return False

        adapter = get_adapter(application)
        if hard:
            await db.delete(memory)
            await adapter.delete(application, memory_id)
        else:
            memory.status = MemoryStatus.DELETED
            await adapter.mark_inactive(application, memory_id)
        await db.commit()
        return True

    async def list_namespaces(self, db: AsyncSession, application_id: uuid.UUID) -> list[str]:
        result = await db.execute(
            select(Memory.namespace).where(Memory.application_id == application_id).distinct()
        )
        return sorted(row[0] for row in result.all())


memory_service = MemoryService()

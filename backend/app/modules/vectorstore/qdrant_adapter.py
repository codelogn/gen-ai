"""QdrantAdapter — genuinely new infrastructure.

A per-application Qdrant collection: app_{slug}_g{generation}, vector size
= embedding_dimension, cosine distance, point ID = memories.id, with a
minimal payload (application_id, namespace, subject_id, status) so
Qdrant's own filtering handles status='active' without a round trip back
to Postgres. This is the only adapter requiring a new, separate server
process (see docs/04-vector-store-adapters.md) — Qdrant runs as its own
systemd unit (qdrant.service, loopback-bound) on this host.
"""

import uuid
from typing import Any, Optional

from qdrant_client import AsyncQdrantClient, models

from app.modules.applications.models import Application
from app.modules.vectorstore.base import VectorMatch, VectorStoreAdapter


def _collection_name(application: Application) -> str:
    slug_part = application.slug.replace("-", "_")
    return f"app_{slug_part}_g{application.vector_backend_generation}"


class QdrantAdapter(VectorStoreAdapter):
    def __init__(self, url: str = "http://127.0.0.1:6333") -> None:
        self._url = url

    def _client(self, application: Application) -> AsyncQdrantClient:
        # An application's vector_backend_config can override the Qdrant
        # URL (e.g. a remote/managed Qdrant instance) — falls back to the
        # local systemd-managed instance otherwise.
        url = (application.vector_backend_config or {}).get("url", self._url)
        return AsyncQdrantClient(url=url)

    async def provision(self, application: Application, dimension: int) -> None:
        client = self._client(application)
        try:
            collection = _collection_name(application)
            if not await client.collection_exists(collection):
                await client.create_collection(
                    collection_name=collection,
                    vectors_config=models.VectorParams(
                        size=dimension, distance=models.Distance.COSINE
                    ),
                )
        finally:
            await client.close()

    async def upsert(
        self,
        application: Application,
        memory_id: uuid.UUID,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        client = self._client(application)
        try:
            await client.upsert(
                collection_name=_collection_name(application),
                points=[
                    models.PointStruct(id=str(memory_id), vector=vector, payload=payload)
                ],
            )
        finally:
            await client.close()

    async def query(
        self,
        application: Application,
        vector: list[float],
        top_k: int,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[VectorMatch]:
        client = self._client(application)
        try:
            collection = _collection_name(application)
            if not await client.collection_exists(collection):
                return []

            must_conditions = [
                models.FieldCondition(key="status", match=models.MatchValue(value="active"))
            ]
            if filters:
                for key, value in filters.items():
                    if value is None:
                        continue
                    must_conditions.append(
                        models.FieldCondition(key=key, match=models.MatchValue(value=value))
                    )

            results = await client.query_points(
                collection_name=collection,
                query=vector,
                query_filter=models.Filter(must=must_conditions),
                limit=top_k,
            )
            return [
                VectorMatch(memory_id=uuid.UUID(str(point.id)), score=float(point.score))
                for point in results.points
            ]
        finally:
            await client.close()

    async def mark_inactive(self, application: Application, memory_id: uuid.UUID) -> None:
        client = self._client(application)
        try:
            collection = _collection_name(application)
            if not await client.collection_exists(collection):
                return
            await client.set_payload(
                collection_name=collection,
                payload={"status": "inactive"},
                points=[str(memory_id)],
            )
        finally:
            await client.close()

    async def delete(self, application: Application, memory_id: uuid.UUID) -> None:
        client = self._client(application)
        try:
            collection = _collection_name(application)
            if not await client.collection_exists(collection):
                return
            await client.delete(
                collection_name=collection,
                points_selector=models.PointIdsList(points=[str(memory_id)]),
            )
        finally:
            await client.close()

    async def health_check(self, application: Application) -> bool:
        client = self._client(application)
        try:
            await client.get_collections()
            return True
        except Exception:
            return False
        finally:
            await client.close()


_qdrant_adapter = QdrantAdapter()


def get_qdrant_adapter() -> QdrantAdapter:
    return _qdrant_adapter

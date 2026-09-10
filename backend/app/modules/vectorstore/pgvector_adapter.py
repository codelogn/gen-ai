"""PgvectorAdapter — shares infrastructure with the control plane.

A per-application table in the same control-plane Postgres DB:
memory_vectors_{slug}_g{generation} (a vector(dim) column + an HNSW index).
Introduces the next level of complexity beyond SqliteVecAdapter: sharing a
server process (already running, for the control-plane data) rather than a
dedicated file. See docs/04-vector-store-adapters.md.

Table/column names are generated from `application.slug`, which is
validated at Application-creation time (schemas.py's SLUG_PATTERN —
lowercase alphanumeric + hyphens only) specifically so it's safe to
interpolate into DDL/identifiers here without a SQL-injection risk.
"""

import re
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.modules.applications.models import Application
from app.modules.vectorstore.base import VectorMatch, VectorStoreAdapter

_IDENTIFIER_SAFE = re.compile(r"^[a-z0-9_]+$")


def _table_name(application: Application) -> str:
    slug_part = application.slug.replace("-", "_")
    name = f"memory_vectors_{slug_part}_g{application.vector_backend_generation}"
    if not _IDENTIFIER_SAFE.match(name):
        # Should be unreachable given SLUG_PATTERN's validation at the API
        # boundary, but never interpolate an unchecked value into DDL.
        raise ValueError(f"Unsafe generated table name: {name!r}")
    return name


class PgvectorAdapter(VectorStoreAdapter):
    async def _session(self) -> AsyncSession:
        return AsyncSessionLocal()

    async def provision(self, application: Application, dimension: int) -> None:
        table = _table_name(application)
        async with await self._session() as db:
            await db.execute(
                text(
                    f'CREATE TABLE IF NOT EXISTS "{table}" ('
                    f"memory_id UUID PRIMARY KEY, "
                    f"embedding vector({dimension}) NOT NULL, "
                    f"is_active BOOLEAN NOT NULL DEFAULT true, "
                    f"namespace TEXT NOT NULL DEFAULT '', "
                    f"subject_id TEXT"
                    f")"
                )
            )
            await db.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS "{table}_hnsw_idx" ON "{table}" '
                    f"USING hnsw (embedding vector_cosine_ops)"
                )
            )
            await db.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS "{table}_namespace_idx" ON "{table}" '
                    f"(namespace, is_active)"
                )
            )
            await db.commit()

    async def upsert(
        self,
        application: Application,
        memory_id: uuid.UUID,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        table = _table_name(application)
        vector_literal = "[" + ",".join(str(x) for x in vector) + "]"
        async with await self._session() as db:
            await db.execute(
                text(
                    f'INSERT INTO "{table}" (memory_id, embedding, is_active, namespace, subject_id) '
                    f"VALUES (:memory_id, :vector, true, :namespace, :subject_id) "
                    f"ON CONFLICT (memory_id) DO UPDATE SET embedding = :vector, is_active = true, "
                    f"namespace = :namespace, subject_id = :subject_id"
                ),
                {
                    "memory_id": str(memory_id),
                    "vector": vector_literal,
                    "namespace": payload.get("namespace", ""),
                    "subject_id": payload.get("subject_id"),
                },
            )
            await db.commit()

    async def query(
        self,
        application: Application,
        vector: list[float],
        top_k: int,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[VectorMatch]:
        table = _table_name(application)
        vector_literal = "[" + ",".join(str(x) for x in vector) + "]"
        async with await self._session() as db:
            exists = await db.execute(
                text("SELECT to_regclass(:table_name) IS NOT NULL"),
                {"table_name": table},
            )
            if not exists.scalar():
                return []

            filters = filters or {}
            where_clauses = ["is_active = true"]
            params: dict[str, Any] = {"vector": vector_literal, "top_k": top_k}
            if filters.get("namespace") is not None:
                where_clauses.append("namespace = :namespace")
                params["namespace"] = filters["namespace"]
            if filters.get("subject_id") is not None:
                where_clauses.append("subject_id = :subject_id")
                params["subject_id"] = filters["subject_id"]

            result = await db.execute(
                text(
                    f'SELECT memory_id, 1 - (embedding <=> :vector) AS score FROM "{table}" '
                    f"WHERE {' AND '.join(where_clauses)} "
                    f"ORDER BY embedding <=> :vector LIMIT :top_k"
                ),
                params,
            )
            return [
                VectorMatch(memory_id=uuid.UUID(str(row.memory_id)), score=float(row.score))
                for row in result.all()
            ]

    async def mark_inactive(self, application: Application, memory_id: uuid.UUID) -> None:
        table = _table_name(application)
        async with await self._session() as db:
            exists = await db.execute(
                text("SELECT to_regclass(:table_name) IS NOT NULL"), {"table_name": table}
            )
            if not exists.scalar():
                return
            await db.execute(
                text(f'UPDATE "{table}" SET is_active = false WHERE memory_id = :memory_id'),
                {"memory_id": str(memory_id)},
            )
            await db.commit()

    async def delete(self, application: Application, memory_id: uuid.UUID) -> None:
        table = _table_name(application)
        async with await self._session() as db:
            exists = await db.execute(
                text("SELECT to_regclass(:table_name) IS NOT NULL"), {"table_name": table}
            )
            if not exists.scalar():
                return
            await db.execute(
                text(f'DELETE FROM "{table}" WHERE memory_id = :memory_id'),
                {"memory_id": str(memory_id)},
            )
            await db.commit()

    async def health_check(self, application: Application) -> bool:
        try:
            async with await self._session() as db:
                await db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


_pgvector_adapter = PgvectorAdapter()


def get_pgvector_adapter() -> PgvectorAdapter:
    return _pgvector_adapter

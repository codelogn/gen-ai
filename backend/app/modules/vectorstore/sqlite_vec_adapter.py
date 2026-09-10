"""SqliteVecAdapter — the simplest possible storage backend.

Uses the sqlite-vec extension's vec0 virtual table for vector storage/KNN
search — no server process at all, just a local file per application:
data/vectors/{slug}_g{generation}.db. No network hop, no connection pool,
no separate service to run or monitor. See docs/04-vector-store-adapters.md.
"""

import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

import sqlite_vec

from app.core.config import settings
from app.modules.applications.models import Application
from app.modules.vectorstore.base import VectorMatch, VectorStoreAdapter


class SqliteVecAdapter(VectorStoreAdapter):
    def _db_path(self, application: Application) -> Path:
        data_dir = Path(settings.VECTOR_DATA_DIR)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / f"{application.slug}_g{application.vector_backend_generation}.db"

    def _connect(self, application: Application) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path(application))
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn

    async def provision(self, application: Application, dimension: int) -> None:
        conn = self._connect(application)
        try:
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0("
                f"memory_id TEXT PRIMARY KEY, embedding FLOAT[{dimension}] distance_metric=cosine)"
            )
            # vec0 tables are vector-only — a plain side table carries the
            # active/inactive status flag AND namespace/subject_id, so
            # query() can filter on all three without a round trip back to
            # the control-plane DB. namespace filtering is not optional:
            # without it, a KNN search returns nearest neighbors across the
            # WHOLE application's vector space, not just the requested
            # namespace — see base.py's query() docstring.
            conn.execute(
                "CREATE TABLE IF NOT EXISTS vector_status ("
                "memory_id TEXT PRIMARY KEY, "
                "is_active INTEGER NOT NULL DEFAULT 1, "
                "namespace TEXT NOT NULL DEFAULT '', "
                "subject_id TEXT)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vector_status_namespace "
                "ON vector_status(namespace, is_active)"
            )
            conn.commit()
        finally:
            conn.close()

    async def upsert(
        self,
        application: Application,
        memory_id: uuid.UUID,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        conn = self._connect(application)
        try:
            mid = str(memory_id)
            packed = sqlite_vec.serialize_float32(vector)
            cur = conn.execute("UPDATE vectors SET embedding = ? WHERE memory_id = ?", (packed, mid))
            if cur.rowcount == 0:
                conn.execute("INSERT INTO vectors(memory_id, embedding) VALUES (?, ?)", (mid, packed))
            namespace = payload.get("namespace", "")
            subject_id = payload.get("subject_id")
            conn.execute(
                "INSERT INTO vector_status(memory_id, is_active, namespace, subject_id) "
                "VALUES (?, 1, ?, ?) "
                "ON CONFLICT(memory_id) DO UPDATE SET is_active = 1, namespace = ?, subject_id = ?",
                (mid, namespace, subject_id, namespace, subject_id),
            )
            conn.commit()
        finally:
            conn.close()

    async def query(
        self,
        application: Application,
        vector: list[float],
        top_k: int,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[VectorMatch]:
        if not self._db_path(application).exists():
            return []
        conn = self._connect(application)
        try:
            filters = filters or {}
            namespace = filters.get("namespace")
            subject_id = filters.get("subject_id")

            where_clauses = ["is_active = 1"]
            params: list[Any] = []
            if namespace is not None:
                where_clauses.append("namespace = ?")
                params.append(namespace)
            if subject_id is not None:
                where_clauses.append("subject_id = ?")
                params.append(subject_id)

            allowed_ids = {
                row[0]
                for row in conn.execute(
                    f"SELECT memory_id FROM vector_status WHERE {' AND '.join(where_clauses)}",
                    params,
                ).fetchall()
            }
            if not allowed_ids:
                return []

            packed = sqlite_vec.serialize_float32(vector)
            # Over-fetch generously — the allowed_ids filter (namespace +
            # subject_id + active) can exclude a large fraction of the
            # nearest neighbors, so top_k alone from the KNN query isn't
            # enough headroom. Cap to avoid scanning the whole table on a
            # tiny corpus where allowed_ids is smaller than fetch_k anyway.
            fetch_k = min(max(top_k * 5, top_k + 20), 500)
            rows = conn.execute(
                "SELECT memory_id, distance FROM vectors WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                (packed, fetch_k),
            ).fetchall()

            matches: list[VectorMatch] = []
            for memory_id_str, distance in rows:
                if memory_id_str not in allowed_ids:
                    continue
                # cosine distance -> cosine similarity score (0..1-ish, higher is better)
                score = 1.0 - float(distance)
                matches.append(VectorMatch(memory_id=uuid.UUID(memory_id_str), score=score))
                if len(matches) >= top_k:
                    break
            return matches
        finally:
            conn.close()

    async def mark_inactive(self, application: Application, memory_id: uuid.UUID) -> None:
        if not self._db_path(application).exists():
            return
        conn = self._connect(application)
        try:
            conn.execute(
                "UPDATE vector_status SET is_active = 0 WHERE memory_id = ?",
                (str(memory_id),),
            )
            conn.commit()
        finally:
            conn.close()

    async def delete(self, application: Application, memory_id: uuid.UUID) -> None:
        if not self._db_path(application).exists():
            return
        conn = self._connect(application)
        try:
            mid = str(memory_id)
            conn.execute("DELETE FROM vectors WHERE memory_id = ?", (mid,))
            conn.execute("DELETE FROM vector_status WHERE memory_id = ?", (mid,))
            conn.commit()
        finally:
            conn.close()

    async def health_check(self, application: Application) -> bool:
        try:
            conn = self._connect(application)
            conn.execute("SELECT 1").fetchone()
            conn.close()
            return True
        except Exception:
            return False

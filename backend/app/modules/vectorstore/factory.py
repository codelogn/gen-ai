"""get_adapter(application) -> VectorStoreAdapter

The one place that decides which concrete VectorStoreAdapter implementation
handles a given application's vector_backend choice.
"""

from app.modules.applications.models import Application, VectorBackend
from app.modules.vectorstore.base import VectorStoreAdapter
from app.modules.vectorstore.sqlite_vec_adapter import SqliteVecAdapter

_sqlite_vec_adapter = SqliteVecAdapter()


def get_adapter(application: Application) -> VectorStoreAdapter:
    if application.vector_backend == VectorBackend.SQLITE_VEC:
        return _sqlite_vec_adapter
    elif application.vector_backend == VectorBackend.PGVECTOR:
        from app.modules.vectorstore.pgvector_adapter import get_pgvector_adapter

        return get_pgvector_adapter()
    elif application.vector_backend == VectorBackend.QDRANT:
        from app.modules.vectorstore.qdrant_adapter import get_qdrant_adapter

        return get_qdrant_adapter()
    else:
        raise ValueError(f"Unsupported vector backend: {application.vector_backend}")

"""The Application (tenant) model.

Every registered consumer of this service is one row here. It drives all
three admin-configurable, per-application choices: where vectors are
stored (vector_backend), how search works (retrieval_strategy), and which
embedding provider generates the vectors (embedding_provider). See
docs/02-multi-tenancy-and-adapters.md for the full design rationale.
"""

import enum
import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VectorBackend(str, enum.Enum):
    SQLITE_VEC = "sqlite_vec"
    PGVECTOR = "pgvector"
    QDRANT = "qdrant"


class RetrievalStrategyName(str, enum.Enum):
    NATIVE = "native"
    LANGCHAIN = "langchain"
    RERANKED = "reranked"


class EmbeddingProviderName(str, enum.Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered consumer of the gen-ai service."""

    __tablename__ = "applications"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Storage adapter (dropdown #1) ---
    vector_backend: Mapped[VectorBackend] = mapped_column(
        String(20), nullable=False, default=VectorBackend.SQLITE_VEC
    )
    vector_backend_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    vector_backend_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    vector_backend_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Retrieval strategy (dropdown #2) ---
    retrieval_strategy: Mapped[RetrievalStrategyName] = mapped_column(
        String(20), nullable=False, default=RetrievalStrategyName.NATIVE
    )
    retrieval_strategy_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # --- Embedding provider (dropdown #3) ---
    embedding_provider: Mapped[EmbeddingProviderName] = mapped_column(
        String(20), nullable=False, default=EmbeddingProviderName.OLLAMA
    )
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, default="nomic-embed-text")
    embedding_base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embedding_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_dimension: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # --- Evaluation judge LLM (dropdown #4) ---
    # A genuinely new capability: gen-ai has only ever embedded text before
    # this (EmbeddingProviderRegistry). Ragas/DeepEval's metrics work via
    # LLM-as-judge, which needs a chat-completion model, not an embedding
    # one — see docs/15-evaluation-frameworks.md. Mirrors the embedding_*
    # fields' shape exactly; reuses EmbeddingProviderName since both
    # capabilities support the same two providers (ollama/openai), even
    # though the model named here must be chat-capable, not an embedding model.
    judge_llm_provider: Mapped[Optional[EmbeddingProviderName]] = mapped_column(String(20), nullable=True)
    judge_llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    judge_llm_base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    judge_llm_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Rate limiting ---
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # --- Audit ---
    created_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )

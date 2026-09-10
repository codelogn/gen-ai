import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.applications.models import (
    EmbeddingProviderName,
    RetrievalStrategyName,
    VectorBackend,
)

SLUG_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")


class ApplicationCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=200)

    vector_backend: VectorBackend = VectorBackend.SQLITE_VEC
    vector_backend_config: Optional[dict] = None
    vector_backend_secret: Optional[str] = None  # plaintext in, encrypted at rest

    retrieval_strategy: RetrievalStrategyName = RetrievalStrategyName.NATIVE
    retrieval_strategy_config: Optional[dict] = None

    embedding_provider: EmbeddingProviderName = EmbeddingProviderName.OLLAMA
    embedding_model: str = Field(default="nomic-embed-text", max_length=100)
    embedding_base_url: Optional[str] = Field(default=None, max_length=255)
    embedding_api_key: Optional[str] = None  # plaintext in, encrypted at rest

    # Evaluation judge LLM — optional at creation; only needed to run
    # judge-LLM-based evaluation frameworks (ragas, deepeval). See
    # docs/15-evaluation-frameworks.md.
    judge_llm_provider: Optional[EmbeddingProviderName] = None
    judge_llm_model: Optional[str] = Field(default=None, max_length=100)
    judge_llm_base_url: Optional[str] = Field(default=None, max_length=255)
    judge_llm_api_key: Optional[str] = None  # plaintext in, encrypted at rest

    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric with optional hyphens "
                "(e.g. 'demo-chat') — it's used to name generated files/tables/collections"
            )
        return v


class ApplicationUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    is_active: Optional[bool] = None

    vector_backend: Optional[VectorBackend] = None
    vector_backend_config: Optional[dict] = None
    vector_backend_secret: Optional[str] = None

    retrieval_strategy: Optional[RetrievalStrategyName] = None
    retrieval_strategy_config: Optional[dict] = None

    embedding_provider: Optional[EmbeddingProviderName] = None
    embedding_model: Optional[str] = Field(default=None, max_length=100)
    embedding_base_url: Optional[str] = Field(default=None, max_length=255)
    embedding_api_key: Optional[str] = None

    judge_llm_provider: Optional[EmbeddingProviderName] = None
    judge_llm_model: Optional[str] = Field(default=None, max_length=100)
    judge_llm_base_url: Optional[str] = Field(default=None, max_length=255)
    judge_llm_api_key: Optional[str] = None

    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1)


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    slug: str
    display_name: str
    is_active: bool

    vector_backend: VectorBackend
    vector_backend_generation: int
    vector_backend_config: Optional[dict] = None

    retrieval_strategy: RetrievalStrategyName
    retrieval_strategy_config: Optional[dict] = None

    embedding_provider: EmbeddingProviderName
    embedding_model: str
    embedding_base_url: Optional[str] = None
    embedding_dimension: Optional[int] = None

    judge_llm_provider: Optional[EmbeddingProviderName] = None
    judge_llm_model: Optional[str] = None
    judge_llm_base_url: Optional[str] = None

    rate_limit_per_minute: Optional[int] = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BackendSwitchWarning(BaseModel):
    """Attached to an ApplicationResponse-affecting PATCH when the change
    bumps vector_backend_generation — see docs/04-vector-store-adapters.md."""

    warning: str

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.memory.models import MemoryStatus

NAMESPACE_PATTERN_MAX_LEN = 128
SUBJECT_ID_MAX_LEN = 255


class MemoryCreate(BaseModel):
    namespace: str = Field(..., min_length=1, max_length=NAMESPACE_PATTERN_MAX_LEN)
    subject_id: Optional[str] = Field(default=None, max_length=SUBJECT_ID_MAX_LEN)
    content: str = Field(..., min_length=1)
    metadata: Optional[dict] = None
    source_ref: Optional[str] = Field(default=None, max_length=255)

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        if any(c in v for c in ("/", "\\", "\x00")):
            raise ValueError("namespace cannot contain '/', '\\\\', or null bytes")
        return v


class MemoryBatchCreate(BaseModel):
    items: list[MemoryCreate] = Field(..., min_length=1, max_length=100)


class MemorySupersede(BaseModel):
    content: str = Field(..., min_length=1)
    metadata: Optional[dict] = None


class MemoryResponse(BaseModel):
    id: uuid.UUID
    namespace: str
    subject_id: Optional[str] = None
    content: str
    # validation_alias points this at the ORM's `metadata_` attribute —
    # the Memory model can't use the plain name `metadata` for its column
    # attribute because SQLAlchemy's declarative Base reserves that name
    # for its own MetaData registry (Base.metadata). The public API field
    # stays "metadata"; only the ORM attribute lookup is redirected.
    metadata: Optional[dict] = Field(default=None, validation_alias="metadata_")
    status: MemoryStatus
    superseded_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class MemorySearchRequest(BaseModel):
    namespace: str = Field(..., min_length=1, max_length=NAMESPACE_PATTERN_MAX_LEN)
    subject_id: Optional[str] = Field(default=None, max_length=SUBJECT_ID_MAX_LEN)
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: Optional[float] = None


class SearchResultResponse(BaseModel):
    id: uuid.UUID
    content: str
    metadata: Optional[dict] = None
    score: float
    created_at: str


class MemorySearchResponse(BaseModel):
    results: list[SearchResultResponse]


class BatchCreateResponse(BaseModel):
    created: list[uuid.UUID]
    failed: list[dict]

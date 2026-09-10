import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)


class ApiKeyCreateResponse(BaseModel):
    id: uuid.UUID
    full_key: str  # shown exactly once — never stored, never re-displayable
    key_prefix: str
    last_four: str
    label: str


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    key_prefix: str
    last_four: str
    label: str
    is_active: bool
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

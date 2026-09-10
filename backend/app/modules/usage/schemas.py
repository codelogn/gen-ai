import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RequestLogResponse(BaseModel):
    id: uuid.UUID
    request_id: str
    method: str
    path: str
    status_code: int
    latency_ms: int
    retrieval_strategy: Optional[str] = None
    vector_backend: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageSummaryResponse(BaseModel):
    window: str
    total_requests: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    p95_latency_ms: float

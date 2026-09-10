import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EvaluationCaseInput(BaseModel):
    query: str = Field(..., min_length=1)
    namespace: str = Field(..., min_length=1)
    subject_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    expected_memory_ids: Optional[list[uuid.UUID]] = None
    expected_context: Optional[str] = None
    generated_answer: Optional[str] = None


class EvaluationRunRequest(BaseModel):
    frameworks: list[str] = Field(..., min_length=1)
    cases: list[EvaluationCaseInput] = Field(..., min_length=1, max_length=50)


class EvaluationRunResponse(BaseModel):
    id: uuid.UUID
    status: str
    frameworks: list[str]
    report: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

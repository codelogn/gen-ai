"""EvaluationRun — one table, not three.

Evaluation runs are diagnostic/on-demand, not high-throughput production
traffic — the same pragmatic-schema instinct already used for the generic
`memories` table applies here: the whole report lives as JSON on one row,
rather than normalizing cases/results into separate tables with no
present need for cross-run analytical queries. See
docs/15-evaluation-frameworks.md.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_runs"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frameworks: Mapped[list] = mapped_column(JSONB, nullable=False)  # e.g. ["native", "ragas", "deepeval"]
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|running|completed|failed
    input_cases: Mapped[list] = mapped_column(JSONB, nullable=False)  # the request as submitted
    report: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # filled in once completed
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

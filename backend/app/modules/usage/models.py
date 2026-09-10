"""IdempotencyKey and RequestLog — both introduced in Phase 6/7.

IdempotencyKey: short-TTL cache of (application, key) -> prior response, so
replaying an identical Idempotency-Key on a write endpoint doesn't
duplicate a row. RequestLog: durable per-request trace for troubleshooting
— see docs/09-observability-and-troubleshooting.md.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IdempotencyKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "idempotency_keys"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class RequestLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "request_logs"

    application_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # Which retrieval strategy/vector backend actually served this request
    # — so comparing native vs langchain results later uses what was
    # actually served, not just whatever the application's current config
    # says (which could have changed since).
    retrieval_strategy: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    vector_backend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

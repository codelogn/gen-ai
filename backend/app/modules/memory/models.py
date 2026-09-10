"""The generic Memory model — one table for every application and every
use case, regardless of which vector backend or retrieval strategy that
application uses. See docs/03-memory-data-model.md for the design
rationale and the honest generic-vs-per-use-case tradeoff.
"""

import enum
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemoryStatus(str, enum.Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


class Memory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memories"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # A logical grouping the calling application defines for its own data
    # (e.g. "messages", "documents") — this service never interprets it.
    namespace: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # An opaque identifier for whatever entity within the calling app this
    # memory belongs to (a conversation id, a user id, ...). Never a real
    # FK — it's another system's own identifier, not ours to validate.
    subject_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    status: Mapped[MemoryStatus] = mapped_column(String(20), nullable=False, default=MemoryStatus.ACTIVE)
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="SET NULL"), nullable=True
    )

    # Opaque traceability string the calling app can stash for its own
    # purposes — never parsed or queried by this service.
    source_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Copied from applications.vector_backend_generation at write time, so
    # a query can cheaply exclude rows written under a since-abandoned
    # backend generation even before that store is physically gone.
    vector_backend_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

"""Idempotency-Key handling for write endpoints.

A short-TTL cache of (application, key) -> prior response, so replaying an
identical Idempotency-Key on POST /memories, /memories/batch, or
/{id}/supersede doesn't create a duplicate row. GET/search/delete don't
need this: search has no side effect, delete is naturally idempotent.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.usage.models import IdempotencyKey

TTL_HOURS = 24


async def get_cached_response(
    db: AsyncSession, application: Application, idempotency_key: Optional[str]
) -> Optional[tuple[int, dict]]:
    if not idempotency_key:
        return None
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.application_id == application.id,
            IdempotencyKey.idempotency_key == idempotency_key,
            IdempotencyKey.expires_at > datetime.now(timezone.utc),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return row.status_code, row.response_body


async def store_response(
    db: AsyncSession,
    application: Application,
    idempotency_key: Optional[str],
    status_code: int,
    response_body: dict,
) -> None:
    if not idempotency_key:
        return
    db.add(
        IdempotencyKey(
            application_id=application.id,
            idempotency_key=idempotency_key,
            status_code=status_code,
            response_body=response_body,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=TTL_HOURS),
        )
    )
    await db.commit()


async def purge_expired(db: AsyncSession) -> int:
    """Housekeeping — not scheduled automatically in V1 (no background job
    runner exists yet); call periodically or on a cron if the table grows
    large enough to matter."""
    result = await db.execute(
        delete(IdempotencyKey).where(IdempotencyKey.expires_at <= datetime.now(timezone.utc))
    )
    await db.commit()
    return result.rowcount or 0


def idempotency_key_header(
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")
) -> Optional[str]:
    return idempotency_key

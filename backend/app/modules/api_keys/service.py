"""API key issuance and verification.

Keys are generated with secrets.token_urlsafe (256 bits of entropy),
hashed with plain sha256 at rest. See docs/07-auth-and-api-keys.md for why
this is a fast hash (not bcrypt) and a hash (not Fernet encryption).
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.api_keys.models import ApplicationApiKey

KEY_PREFIX_TAG = "gak"  # "gen-ai key" — a recognizable prefix, same idea as GitHub's "ghp_"


def _hash_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode()).hexdigest()


class ApiKeyService:
    async def issue(
        self,
        db: AsyncSession,
        application_id: uuid.UUID,
        label: str,
        created_by_admin_id: uuid.UUID,
    ) -> tuple[ApplicationApiKey, str]:
        """Returns (row, full_key). full_key is returned ONLY here — the
        caller must show it to the admin now, since it can never be
        recovered again (only key_hash is stored)."""
        secret_part = secrets.token_urlsafe(32)
        full_key = f"{KEY_PREFIX_TAG}_{secret_part}"
        key_prefix = full_key[:12]
        last_four = full_key[-4:]

        row = ApplicationApiKey(
            application_id=application_id,
            key_prefix=key_prefix,
            key_hash=_hash_key(full_key),
            last_four=last_four,
            label=label,
            is_active=True,
            created_by_admin_id=created_by_admin_id,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row, full_key

    async def list_for_application(
        self, db: AsyncSession, application_id: uuid.UUID
    ) -> list[ApplicationApiKey]:
        result = await db.execute(
            select(ApplicationApiKey)
            .where(ApplicationApiKey.application_id == application_id)
            .order_by(ApplicationApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(
        self, db: AsyncSession, application_id: uuid.UUID, key_id: uuid.UUID
    ) -> bool:
        result = await db.execute(
            select(ApplicationApiKey).where(
                ApplicationApiKey.id == key_id, ApplicationApiKey.application_id == application_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        row.is_active = False
        row.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    async def verify(self, db: AsyncSession, presented_key: str) -> Optional[ApplicationApiKey]:
        """Look up by prefix (indexed, cheap), then compare the full hash.
        Returns the matching, active key row, or None."""
        if not presented_key or len(presented_key) < 12:
            return None
        prefix = presented_key[:12]
        result = await db.execute(
            select(ApplicationApiKey).where(
                ApplicationApiKey.key_prefix == prefix, ApplicationApiKey.is_active == True  # noqa: E712
            )
        )
        candidates = result.scalars().all()
        presented_hash = _hash_key(presented_key)
        for candidate in candidates:
            if secrets.compare_digest(candidate.key_hash, presented_hash):
                candidate.last_used_at = datetime.now(timezone.utc)
                await db.commit()
                return candidate
        return None


api_key_service = ApiKeyService()

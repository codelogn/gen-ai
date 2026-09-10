import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.modules.admin_auth.models import AdminUser


class AdminAuthService:
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[AdminUser]:
        result = await db.execute(select(AdminUser).where(AdminUser.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, db: AsyncSession, admin_id: uuid.UUID) -> Optional[AdminUser]:
        result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
        return result.scalar_one_or_none()

    async def create_admin(self, db: AsyncSession, email: str, password: str) -> AdminUser:
        admin = AdminUser(email=email, password_hash=hash_password(password), is_active=True)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin

    async def authenticate(self, db: AsyncSession, email: str, password: str) -> Optional[AdminUser]:
        admin = await self.get_by_email(db, email)
        if admin is None or not admin.is_active:
            return None
        if not verify_password(password, admin.password_hash):
            return None
        admin.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(admin)
        return admin


admin_auth_service = AdminAuthService()

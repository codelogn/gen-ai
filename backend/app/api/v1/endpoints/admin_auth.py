import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.rate_limit import enforce_login_rate_limit
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.modules.admin_auth.models import AdminUser
from app.modules.admin_auth.schemas import (
    AdminAccessTokenResponse,
    AdminLoginRequest,
    AdminMeResponse,
    AdminRefreshRequest,
    AdminTokenResponse,
)
from app.modules.admin_auth.service import admin_auth_service

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=AdminTokenResponse, dependencies=[Depends(enforce_login_rate_limit)])
async def login(data: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    admin = await admin_auth_service.authenticate(db, data.email, data.password)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return AdminTokenResponse(
        access_token=create_access_token(admin.id),
        refresh_token=create_refresh_token(admin.id),
    )


@router.post("/refresh", response_model=AdminAccessTokenResponse)
async def refresh(data: AdminRefreshRequest, db: AsyncSession = Depends(get_db)):
    admin_id_str = decode_token(data.refresh_token, expected_type="refresh")
    if admin_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        )
    admin = await admin_auth_service.get_by_id(db, uuid.UUID(admin_id_str))
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer active")
    return AdminAccessTokenResponse(access_token=create_access_token(admin.id))


@router.get("/me", response_model=AdminMeResponse)
async def me(admin: AdminUser = Depends(get_current_admin)):
    return admin

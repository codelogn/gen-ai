import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.modules.admin_auth.models import AdminUser
from app.modules.api_keys.schemas import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from app.modules.api_keys.service import api_key_service
from app.modules.applications.service import application_service

router = APIRouter(prefix="/applications/{application_id}/api-keys", tags=["admin-api-keys"])


async def _require_application(application_id: uuid.UUID, db: AsyncSession):
    app_row = await application_service.get(db, application_id)
    if app_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app_row


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    application_id: uuid.UUID,
    data: ApiKeyCreate,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_application(application_id, db)
    row, full_key = await api_key_service.issue(db, application_id, data.label, admin.id)
    return ApiKeyCreateResponse(
        id=row.id, full_key=full_key, key_prefix=row.key_prefix, last_four=row.last_four,
        label=row.label,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    application_id: uuid.UUID,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_application(application_id, db)
    return await api_key_service.list_for_application(db, application_id)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    application_id: uuid.UUID,
    key_id: uuid.UUID,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_application(application_id, db)
    found = await api_key_service.revoke(db, application_id, key_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

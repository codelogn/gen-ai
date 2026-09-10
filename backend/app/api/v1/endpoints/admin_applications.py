import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.modules.admin_auth.models import AdminUser
from app.modules.applications.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
)
from app.modules.applications.service import application_service

router = APIRouter(prefix="/applications", tags=["admin-applications"])


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    data: ApplicationCreate,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        app_row = await application_service.create(db, data, created_by_admin_id=admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return app_row


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await application_service.list_applications(db)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    app_row = await application_service.get(db, application_id)
    if app_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app_row


@router.patch("/{application_id}")
async def update_application(
    application_id: uuid.UUID,
    data: ApplicationUpdate,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    app_row, warning = await application_service.update(db, application_id, data)
    if app_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    response = ApplicationResponse.model_validate(app_row).model_dump()
    if warning:
        response["warning"] = warning
    return response


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_application(
    application_id: uuid.UUID,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    found = await application_service.deactivate(db, application_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

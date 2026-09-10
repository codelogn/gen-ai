import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.modules.admin_auth.models import AdminUser
from app.modules.applications.service import application_service
from app.modules.evaluation.schemas import EvaluationRunResponse
from app.modules.evaluation.service import evaluation_service
from app.modules.usage.schemas import RequestLogResponse, UsageSummaryResponse
from app.modules.usage.service import usage_service
from app.modules.vectorstore.factory import get_adapter

router = APIRouter(prefix="/applications/{application_id}", tags=["admin-observability"])
health_router = APIRouter(prefix="/health", tags=["admin-observability"])


async def _require_application(application_id: uuid.UUID, db: AsyncSession):
    app_row = await application_service.get(db, application_id)
    if app_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app_row


@router.get("/logs", response_model=list[RequestLogResponse])
async def get_logs(
    application_id: uuid.UUID,
    status_code: Optional[int] = Query(default=None, alias="status"),
    since: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_application(application_id, db)
    return await usage_service.list_logs(
        db, application_id, status_filter=status_code, since=since, limit=limit
    )


@router.get("/usage-summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    application_id: uuid.UUID,
    window: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_application(application_id, db)
    return await usage_service.usage_summary(db, application_id, window=window)


@router.get("/evaluations", response_model=list[EvaluationRunResponse])
async def list_evaluation_runs(
    application_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_application(application_id, db)
    return await evaluation_service.list_runs(db, application_id, limit=limit)


@router.get("/evaluations/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_run_admin(
    application_id: uuid.UUID,
    run_id: uuid.UUID,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _require_application(application_id, db)
    run = await evaluation_service.get_run(db, application_id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return run


@health_router.get("/backends")
async def health_backends(
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    applications = await application_service.list_applications(db)
    results = []
    for app_row in applications:
        if not app_row.is_active:
            continue
        adapter = get_adapter(app_row)
        healthy = await adapter.health_check(app_row)
        results.append(
            {
                "application_id": str(app_row.id),
                "slug": app_row.slug,
                "vector_backend": app_row.vector_backend,
                "healthy": healthy,
            }
        )
    return {"backends": results}

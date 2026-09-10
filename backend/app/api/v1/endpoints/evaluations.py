import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.modules.applications.models import Application
from app.modules.evaluation.schemas import EvaluationRunRequest, EvaluationRunResponse
from app.modules.evaluation.service import evaluation_service

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_evaluation_run(
    data: EvaluationRunRequest,
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    try:
        run = await evaluation_service.run(
            db, application, data.frameworks, [c.model_dump(mode="json") for c in data.cases]
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return run


@router.get("/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_run(
    run_id: uuid.UUID,
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    run = await evaluation_service.get_run(db, application.id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return run

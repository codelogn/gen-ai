"""Server-rendered admin UI — Jinja2 templates inside the FastAPI app,
not a separate frontend project or process (see docs/02-multi-tenancy-and-adapters.md
for why: one human operator doing occasional CRUD and log-reading doesn't
need a build pipeline). The REST admin endpoints underneath
(api/v1/endpoints/admin_*.py) are what these routes call into — this
module is a thin browser-facing layer over the same service functions.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ui_auth import COOKIE_NAME, get_current_admin_ui
from app.modules.admin_auth.models import AdminUser
from app.modules.admin_auth.service import admin_auth_service
from app.modules.api_keys.service import api_key_service
from app.modules.applications.models import Application
from app.modules.applications.schemas import ApplicationCreate, ApplicationUpdate
from app.modules.applications.service import application_service
from app.modules.evaluation.service import evaluation_service
from app.modules.usage.service import usage_service

router = APIRouter(tags=["admin-ui"])

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _ctx(request: Request, admin: AdminUser | None = None, **kwargs) -> dict:
    return {"request": request, "admin": admin, **kwargs}


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", _ctx(request))


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    from app.core.security import create_access_token

    admin = await admin_auth_service.authenticate(db, email, password)
    if admin is None:
        return templates.TemplateResponse(
            "login.html", _ctx(request, error="Invalid email or password"), status_code=401
        )

    response = RedirectResponse(url="/admin/ui/applications", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        create_access_token(admin.id),
        httponly=True,
        samesite="lax",
        max_age=60 * 30,
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/admin/ui/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("")
async def root():
    return RedirectResponse(url="/admin/ui/applications", status_code=303)


@router.get("/applications")
async def applications_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    applications = await application_service.list_applications(db)
    return templates.TemplateResponse(
        "applications_list.html", _ctx(request, admin, applications=applications)
    )


@router.get("/applications/new")
async def application_new_form(
    request: Request, admin: AdminUser = Depends(get_current_admin_ui)
):
    return templates.TemplateResponse(
        "application_form.html", _ctx(request, admin, application=None)
    )


def _parse_application_form(form) -> dict:
    # Hidden (display:none) fields from the OTHER strategy's config block
    # still submit their value even when a different strategy is selected
    # — a pre-existing quirk, not introduced here. Branching on the
    # selected retrieval_strategy itself (rather than "is hybrid_weight
    # truthy") avoids compounding it by also picking up a stray
    # rerank_model/rerank_candidate_pool value left over from a form that
    # was displaying reranked-fields before the user switched strategies.
    strategy = form.get("retrieval_strategy")
    retrieval_strategy_config = None
    if strategy == "langchain":
        hybrid_weight = form.get("hybrid_keyword_weight")
        if hybrid_weight:
            retrieval_strategy_config = {"hybrid_keyword_weight": float(hybrid_weight)}
    elif strategy == "reranked":
        rerank_model = form.get("rerank_model")
        rerank_pool = form.get("rerank_candidate_pool")
        retrieval_strategy_config = {
            k: v
            for k, v in {
                "rerank_model": rerank_model or None,
                "rerank_candidate_pool": int(rerank_pool) if rerank_pool else None,
            }.items()
            if v is not None
        } or None

    rate_limit = form.get("rate_limit_per_minute")
    return {
        "display_name": form.get("display_name"),
        "vector_backend": form.get("vector_backend"),
        "retrieval_strategy": form.get("retrieval_strategy"),
        "retrieval_strategy_config": retrieval_strategy_config,
        "embedding_provider": form.get("embedding_provider"),
        "embedding_model": form.get("embedding_model"),
        "embedding_base_url": form.get("embedding_base_url") or None,
        "embedding_api_key": form.get("embedding_api_key") or None,
        # judge_llm_provider's "(not configured)" option submits an empty
        # string — must become None, not the literal "", to pass the
        # EmbeddingProviderName enum validation (or correctly clear it on edit).
        "judge_llm_provider": form.get("judge_llm_provider") or None,
        "judge_llm_model": form.get("judge_llm_model") or None,
        "judge_llm_base_url": form.get("judge_llm_base_url") or None,
        "judge_llm_api_key": form.get("judge_llm_api_key") or None,
        "rate_limit_per_minute": int(rate_limit) if rate_limit else None,
    }


@router.post("/applications/new")
async def application_create(
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = ApplicationCreate(slug=form.get("slug"), **_parse_application_form(form))
    try:
        app_row = await application_service.create(db, data, created_by_admin_id=admin.id)
    except ValueError as exc:
        applications = await application_service.list_applications(db)
        return templates.TemplateResponse(
            "applications_list.html",
            _ctx(request, admin, applications=applications, flashes=[(str(exc), "error")]),
            status_code=409,
        )
    return RedirectResponse(url=f"/admin/ui/applications/{app_row.id}", status_code=303)


async def _get_application_or_404(application_id: uuid.UUID, db: AsyncSession) -> Application:
    app_row = await application_service.get(db, application_id)
    if app_row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app_row


@router.get("/applications/{application_id}")
async def application_detail(
    application_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    app_row = await _get_application_or_404(application_id, db)
    api_keys = await api_key_service.list_for_application(db, application_id)
    return templates.TemplateResponse(
        "application_detail.html", _ctx(request, admin, application=app_row, api_keys=api_keys)
    )


@router.get("/applications/{application_id}/edit")
async def application_edit_form(
    application_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    app_row = await _get_application_or_404(application_id, db)
    return templates.TemplateResponse(
        "application_form.html", _ctx(request, admin, application=app_row)
    )


@router.post("/applications/{application_id}/edit")
async def application_edit_submit(
    application_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = ApplicationUpdate(**_parse_application_form(form))
    app_row, warning = await application_service.update(db, application_id, data)
    app_row = await _get_application_or_404(application_id, db)
    api_keys = await api_key_service.list_for_application(db, application_id)
    flashes = [(warning, "warning")] if warning else [("Application updated.", "success")]
    return templates.TemplateResponse(
        "application_detail.html",
        _ctx(request, admin, application=app_row, api_keys=api_keys, flashes=flashes),
    )


@router.post("/applications/{application_id}/api-keys")
async def application_issue_key(
    application_id: uuid.UUID,
    request: Request,
    label: str = Form(...),
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    app_row = await _get_application_or_404(application_id, db)
    _, full_key = await api_key_service.issue(db, application_id, label, admin.id)
    api_keys = await api_key_service.list_for_application(db, application_id)
    return templates.TemplateResponse(
        "application_detail.html",
        _ctx(request, admin, application=app_row, api_keys=api_keys, revealed_key=full_key),
    )


@router.post("/applications/{application_id}/api-keys/{key_id}/revoke")
async def application_revoke_key(
    application_id: uuid.UUID,
    key_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    await api_key_service.revoke(db, application_id, key_id)
    return RedirectResponse(url=f"/admin/ui/applications/{application_id}", status_code=303)


@router.get("/applications/{application_id}/logs")
async def application_logs(
    application_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    app_row = await _get_application_or_404(application_id, db)
    logs = await usage_service.list_logs(db, application_id, limit=100)
    usage = await usage_service.usage_summary(db, application_id, window="24h")
    return templates.TemplateResponse(
        "application_logs.html", _ctx(request, admin, application=app_row, logs=logs, usage=usage)
    )


@router.get("/applications/{application_id}/evaluations")
async def application_evaluations(
    application_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    app_row = await _get_application_or_404(application_id, db)
    runs = await evaluation_service.list_runs(db, application_id, limit=50)
    return templates.TemplateResponse(
        "application_evaluations.html", _ctx(request, admin, application=app_row, runs=runs)
    )


@router.post("/applications/{application_id}/evaluations")
async def application_evaluations_create(
    application_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    import json

    app_row = await _get_application_or_404(application_id, db)
    form = await request.form()
    frameworks = form.getlist("frameworks") or ["native"]

    try:
        cases = json.loads(form.get("cases_json", "[]"))
    except json.JSONDecodeError as exc:
        runs = await evaluation_service.list_runs(db, application_id, limit=50)
        return templates.TemplateResponse(
            "application_evaluations.html",
            _ctx(request, admin, application=app_row, runs=runs,
                 flashes=[(f"Invalid test-cases JSON: {exc}", "error")]),
            status_code=400,
        )

    # Drop empty-string placeholder values from the textarea's example
    # template so an unedited "expected_context": "" doesn't get treated
    # as "provided" by the frameworks that check truthiness.
    for case in cases:
        for key in ("expected_context", "generated_answer", "subject_id"):
            if case.get(key) == "":
                case[key] = None
        if not case.get("expected_memory_ids"):
            case["expected_memory_ids"] = None

    try:
        run = await evaluation_service.run(db, app_row, frameworks, cases)
    except ValueError as exc:
        runs = await evaluation_service.list_runs(db, application_id, limit=50)
        return templates.TemplateResponse(
            "application_evaluations.html",
            _ctx(request, admin, application=app_row, runs=runs, flashes=[(str(exc), "error")]),
            status_code=400,
        )

    return RedirectResponse(
        url=f"/admin/ui/applications/{application_id}/evaluations/{run.id}", status_code=303
    )


@router.get("/applications/{application_id}/evaluations/{run_id}")
async def application_evaluation_detail(
    application_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(get_current_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    app_row = await _get_application_or_404(application_id, db)
    run = await evaluation_service.get_run(db, application_id, run_id)
    if run is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return templates.TemplateResponse(
        "evaluation_run_detail.html", _ctx(request, admin, application=app_row, run=run)
    )

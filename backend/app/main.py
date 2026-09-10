"""gen-ai service entry point.

A shared AI memory / RAG microservice. See /docs for the full architecture
and design rationale.
"""

import logging

from fastapi import FastAPI, Request, Response, status
from sqlalchemy import text

from app.admin_ui.routes import router as admin_ui_router
from app.api.v1.endpoints import (
    admin_api_keys,
    admin_applications,
    admin_auth,
    admin_logs,
    evaluations,
    memories,
)
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.ui_auth import RedirectToLogin, redirect_to_login
from app.modules.usage.middleware import RequestLoggingMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="gen-ai",
    description="Shared AI memory & RAG microservice",
    version="0.1.0",
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(admin_auth.router, prefix=settings.ADMIN_API_V1_PREFIX)
app.include_router(admin_applications.router, prefix=settings.ADMIN_API_V1_PREFIX)
app.include_router(admin_api_keys.router, prefix=settings.ADMIN_API_V1_PREFIX)
app.include_router(admin_logs.router, prefix=settings.ADMIN_API_V1_PREFIX)
app.include_router(admin_logs.health_router, prefix=settings.ADMIN_API_V1_PREFIX)
app.include_router(memories.router, prefix=settings.API_V1_PREFIX)
app.include_router(memories.namespaces_router, prefix=settings.API_V1_PREFIX)
app.include_router(evaluations.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_ui_router, prefix="/admin/ui")


@app.exception_handler(RedirectToLogin)
async def _redirect_to_login_handler(request: Request, exc: RedirectToLogin):
    return redirect_to_login()


@app.get("/health", tags=["system"])
async def health():
    """Liveness only — always 200 if the process is up.

    Does not check the database or any configured backend; see /ready for
    that. Orchestration should use /health to decide "should I restart
    this process" and /ready to decide "should I route traffic to it."
    """
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def ready(response: Response):
    """Readiness — checks control-plane DB connectivity. Returns 503 if
    unreachable, so orchestration/reverse-proxy health checks can tell
    "merely up" apart from "can actually serve requests" — a distinction
    /health alone can't make."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "unreachable", "error": str(exc)[:300]}

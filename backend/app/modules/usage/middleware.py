"""Durable per-request logging middleware.

Writes one RequestLog row per request through the API, including which
application/backend/strategy actually served it (read from request.state,
set by get_current_application — see app/core/deps.py). This is the
service's answer to "why did app X's memory search just fail" — a SQL
table an admin can query, not an in-memory-only trace that vanishes on
restart. See docs/09-observability-and-troubleshooting.md.
"""

import logging
import time
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("gen_ai.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        error_detail = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:  # noqa: BLE001 — log then re-raise, don't swallow
            status_code = 500
            error_detail = str(exc)[:1000]
            latency_ms = int((time.perf_counter() - start) * 1000)
            await self._write_log(request, request_id, status_code, latency_ms, error_detail)
            logger.exception(f"[{request_id}] Unhandled exception on {request.method} {request.url.path}")
            raise

        latency_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        # error_detail stays None here for ordinary 4xx responses (401,
        # 404, 429, validation errors) — those are handled by FastAPI's
        # normal exception handling before call_next() returns, so this
        # middleware never sees them as exceptions. Their detail is
        # already in the response body the caller receives; capturing it
        # here too would mean re-reading and reconstructing the response
        # body stream, which isn't worth the complexity for what's already
        # visible in the status code + path. error_detail is populated
        # only for the truly-unhandled-exception case above.

        # Fire-and-forget-ish: awaited so it's still durable, but failures
        # here must never break the actual response the caller is waiting on.
        try:
            await self._write_log(request, request_id, status_code, latency_ms, error_detail)
        except Exception:
            logger.exception(f"[{request_id}] Failed to write request log")

        logger.info(
            f"[{request_id}] {request.method} {request.url.path} -> {status_code} ({latency_ms}ms)"
        )
        return response

    async def _write_log(
        self, request: Request, request_id: str, status_code: int, latency_ms: int, error_detail
    ) -> None:
        # Only log requests that actually resolved to an application or an
        # admin-auth-adjacent path — skip /health noise.
        if request.url.path in ("/health", "/ready"):
            return

        from app.core.database import AsyncSessionLocal  # local import avoids a circular import at module load
        from app.modules.usage.models import RequestLog

        application_id = getattr(request.state, "application_id", None)
        retrieval_strategy = getattr(request.state, "retrieval_strategy_used", None)
        vector_backend = getattr(request.state, "vector_backend_used", None)

        async with AsyncSessionLocal() as db:
            db.add(
                RequestLog(
                    application_id=uuid.UUID(application_id) if application_id else None,
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    retrieval_strategy=retrieval_strategy,
                    vector_backend=vector_backend,
                    error_detail=error_detail,
                    created_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

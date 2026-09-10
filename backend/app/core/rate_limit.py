"""Per-application rate limiting — in-memory sliding window.

Keyed by application_id, not client IP, since the caller is a registered
application (verified via API key), not an anonymous browser. No Redis
needed for a single-process deployment; see docs/10-latest-practices-checklist.md
for when to revisit this (multiple uvicorn workers).
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict, Hashable

from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.deps import get_current_application
from app.modules.applications.models import Application

WINDOW_SECONDS = 60.0

_request_log: Dict[Hashable, Deque[float]] = defaultdict(deque)


def _check_and_record(key: Hashable, limit: int) -> bool:
    now = time.monotonic()
    window = _request_log[key]

    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()

    if len(window) >= limit:
        return False

    window.append(now)
    return True


async def enforce_rate_limit(application: Application = Depends(get_current_application)) -> Application:
    limit = application.rate_limit_per_minute or settings.DEFAULT_RATE_LIMIT_PER_MINUTE
    if not _check_and_record(application.id, limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} requests per minute for this application.",
        )
    return application


# The one place in this service a guessable, human-chosen secret (a
# password) is at risk — brute-force protection keyed by client IP,
# independent of the per-application limiter above.
LOGIN_ATTEMPTS_PER_MINUTE = 10


async def enforce_login_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not _check_and_record(("login", client_ip), LOGIN_ATTEMPTS_PER_MINUTE):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a minute and try again.",
        )

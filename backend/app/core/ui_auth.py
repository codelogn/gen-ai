"""Cookie-based admin auth for the server-rendered UI (app/admin_ui/).

The JSON API (app/api/v1/endpoints/admin_auth.py) uses Authorization:
Bearer for API clients. A browser session doesn't naturally carry that
header on plain page navigations, so the UI stores the same JWT access
token in an HttpOnly cookie instead — same token format/verification
(core/security.py::decode_token), different transport.
"""

import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.modules.admin_auth.models import AdminUser

COOKIE_NAME = "gen_ai_admin_session"


class RedirectToLogin(Exception):
    """Raised instead of HTTPException so UI routes can redirect to the
    login page rather than showing a raw 401 JSON error to a browser."""


async def get_current_admin_ui(
    request: Request, db: AsyncSession = Depends(get_db)
) -> AdminUser:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise RedirectToLogin()

    admin_id_str = decode_token(token, expected_type="access")
    if admin_id_str is None:
        raise RedirectToLogin()

    try:
        admin_id = uuid.UUID(admin_id_str)
    except ValueError:
        raise RedirectToLogin()

    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise RedirectToLogin()
    return admin


def redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url="/admin/ui/login", status_code=303)

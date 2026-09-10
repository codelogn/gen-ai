"""FastAPI dependencies for both auth realms.

get_current_admin / require_admin: the independent admin login realm (JWT).
get_current_application: the API-key realm consumers use (X-API-Key header,
verified against ApplicationApiKey's hashed keys — see
docs/07-auth-and-api-keys.md).
"""

import uuid

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.modules.admin_auth.models import AdminUser
from app.modules.applications.models import Application

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired admin session",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    admin_id_str = decode_token(credentials.credentials, expected_type="access")
    if admin_id_str is None:
        raise unauthorized

    try:
        admin_id = uuid.UUID(admin_id_str)
    except ValueError:
        raise unauthorized

    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise unauthorized

    return admin


async def require_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    """V1 has exactly one flat admin role — this is just an alias making the
    intent explicit at each endpoint, and the natural place to add role
    checks later if a narrower-than-full-access role is ever needed."""
    return admin


async def get_current_application(
    request: Request,
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Application:
    """Real API-key auth (replaces the Phase 2-5 X-Application-Id dev
    stand-in, same signature — nothing above this dependency needed to
    change). Verifies X-API-Key against ApplicationApiKey's hashed keys
    (app/modules/api_keys/service.py::verify) and resolves the owning,
    active Application.

    Stashes primitive values (not the ORM object — it can become detached
    once this request's DB session closes) on request.state so the
    logging middleware (app/modules/usage/middleware.py) can record which
    application/backend/strategy actually served this request, without
    the middleware needing its own DB round trip.
    """
    from app.modules.api_keys.service import api_key_service

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive API key"
    )

    key_row = await api_key_service.verify(db, x_api_key)
    if key_row is None:
        raise unauthorized

    result = await db.execute(select(Application).where(Application.id == key_row.application_id))
    application = result.scalar_one_or_none()
    if application is None or not application.is_active:
        raise unauthorized

    request.state.application_id = str(application.id)
    request.state.retrieval_strategy_used = str(application.retrieval_strategy)
    request.state.vector_backend_used = str(application.vector_backend)
    return application

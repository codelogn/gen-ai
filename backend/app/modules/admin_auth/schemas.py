import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AdminRefreshRequest(BaseModel):
    refresh_token: str


class AdminAccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminMeResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

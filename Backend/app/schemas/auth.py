# app/schemas/auth.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenPayload(BaseModel):
    sub: str
    exp: int
    role: str | None = None

    model_config = ConfigDict(from_attributes=True)

# app/schemas/auth.py
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime | None = None

class TokenPayload(BaseModel):
    sub: str
    exp: int
    role: str | None = None

    model_config = ConfigDict(from_attributes=True)

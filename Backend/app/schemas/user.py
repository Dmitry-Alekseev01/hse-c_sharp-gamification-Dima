"""
app/schemas/user.py
DESCRIPTION: Pydantic DTOs for user endpoints.
Using pydantic v2's ConfigDict to enable reading from ORM models via from_attributes.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import model_validator


UserRole = Literal["user", "teacher", "admin"]


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None


class AdminUserCreate(UserCreate):
    role: UserRole = "user"


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserProfileUpdate(BaseModel):
    username: str | None = None
    full_name: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "UserProfileUpdate":
        if self.username is None and self.full_name is None:
            raise ValueError("At least one field must be provided")
        if self.username is not None and not self.username.strip():
            raise ValueError("username must not be empty")
        return self


class UserRead(BaseModel):
    id: int
    username: str
    full_name: str | None
    role: str
    created_at: datetime | None = None

    # pydantic v2: enable reading from SQLAlchemy objects
    model_config = ConfigDict(from_attributes=True)

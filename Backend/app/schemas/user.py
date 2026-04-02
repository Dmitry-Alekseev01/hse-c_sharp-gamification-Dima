"""
app/schemas/user.py
DESCRIPTION: Pydantic DTOs for user endpoints.
Using pydantic v2's ConfigDict to enable reading from ORM models via from_attributes.
"""
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict


UserRole = Literal["user", "teacher", "admin"]


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None


class AdminUserCreate(UserCreate):
    role: UserRole = "user"


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserRead(BaseModel):
    id: int
    username: str
    full_name: str | None
    role: str

    # pydantic v2: enable reading from SQLAlchemy objects
    model_config = ConfigDict(from_attributes=True)

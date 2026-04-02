# app/repositories/auth_repo.py
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.repositories.user_repo import get_user_by_username, create_user as repo_create_user
from app.core.security import verify_password, get_password_hash
from app.models.user import User


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    full_name: str | None = None,
    role: str = "user",
) -> User:
    password_hash = get_password_hash(password)
    # repo_create_user expects password_hash param
    user = await repo_create_user(
        db,
        username=username,
        password_hash=password_hash,
        full_name=full_name,
        role=role,
    )
    return user

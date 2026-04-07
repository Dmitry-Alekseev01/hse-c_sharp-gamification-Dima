"""User domain service."""
from app.core.security import get_password_hash
from app.repositories import user_repo

async def register_user(
    session,
    username: str,
    password: str,
    full_name: str | None = None,
    role: str = "user",
):
    existing = await user_repo.get_user_by_username(session, username)
    if existing:
        raise ValueError("username already exists")
    pw_hash = get_password_hash(password)
    return await user_repo.create_user(session, username, pw_hash, full_name, role=role)

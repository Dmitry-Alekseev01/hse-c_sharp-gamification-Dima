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


async def update_user_profile(
    session,
    user_id: int,
    *,
    username: str | None = None,
    full_name: str | None = None,
):
    user = await user_repo.get_user_by_id(session, user_id)
    if user is None:
        raise LookupError("User not found")

    next_username = username.strip() if username is not None else None
    if next_username is not None and next_username != user.username:
        existing = await user_repo.get_user_by_username(session, next_username)
        if existing is not None and existing.id != user.id:
            raise ValueError("username already exists")

    return await user_repo.update_user_profile(
        session,
        user,
        username=next_username,
        full_name=full_name,
    )

"""User domain service."""
from app.core.security import get_password_hash, invalidate_auth_user_cache, verify_password
from app.core.password_policy import validate_password_policy
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
    validate_password_policy(password)
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

    previous_username = user.username
    updated_user = await user_repo.update_user_profile(
        session,
        user,
        username=next_username,
        full_name=full_name,
    )
    await invalidate_auth_user_cache(previous_username, updated_user.username)
    return updated_user


async def change_user_password(
    session,
    user_id: int,
    *,
    current_password: str,
    new_password: str,
):
    user = await user_repo.get_user_by_id(session, user_id)
    if user is None:
        raise LookupError("User not found")

    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect")
    if current_password == new_password:
        raise ValueError("New password must differ from current password")
    validate_password_policy(new_password)

    password_hash = get_password_hash(new_password)
    updated_user = await user_repo.update_user_password(session, user, password_hash=password_hash)
    await invalidate_auth_user_cache(updated_user.username)
    return updated_user


async def admin_reset_user_password(
    session,
    user_id: int,
    *,
    new_password: str,
):
    user = await user_repo.get_user_by_id(session, user_id)
    if user is None:
        raise LookupError("User not found")
    validate_password_policy(new_password)

    password_hash = get_password_hash(new_password)
    updated_user = await user_repo.update_user_password(session, user, password_hash=password_hash)
    await invalidate_auth_user_cache(updated_user.username)
    return updated_user


async def delete_user(
    session,
    user_id: int,
):
    user = await user_repo.get_user_by_id(session, user_id)
    if user is None:
        raise LookupError("User not found")
    await user_repo.delete_user(session, user)
    await invalidate_auth_user_cache(user.username)

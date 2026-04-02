"""
app/repositories/user_repo.py
DESCRIPTION: DB access layer for users. Contains only a couple of helpers.
"""
from sqlalchemy import select
from app.models.user import User

async def get_user_by_username(session, username: str):
    q = select(User).where(User.username == username)
    res = await session.execute(q)
    return res.scalars().first()

async def list_users(session, limit: int = 100):
    q = select(User).limit(limit)
    res = await session.execute(q)
    return res.scalars().all()

async def create_user(
    session,
    username: str,
    password_hash: str,
    full_name: str | None = None,
    role: str = "user",
):
    user = User(username=username, password_hash=password_hash, full_name=full_name, role=role)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def get_user_by_id(session, user_id: int):
    return await session.get(User, user_id)

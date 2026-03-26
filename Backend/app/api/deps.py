# app/api/deps.py
"""
Dependency helpers for FastAPI.
Provides get_db() as an async generator (FastAPI compatible).
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a DB session to FastAPI endpoints.
    Use as: db = Depends(get_db)
    This function must be an async generator (yield) — FastAPI will cleanup automatically.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

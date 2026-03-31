# app/api/deps.py
"""
Dependency helpers for FastAPI.
Provides get_db() as an async generator (FastAPI compatible).
"""
import logging
from collections.abc import Awaitable, Callable
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

POST_COMMIT_TASKS_KEY = "post_commit_tasks"


def add_post_commit_task(session: AsyncSession, task_factory: Callable[[], Awaitable[None]]) -> None:
    tasks = session.info.setdefault(POST_COMMIT_TASKS_KEY, [])
    tasks.append(task_factory)


async def run_post_commit_tasks(session: AsyncSession) -> None:
    tasks: list[Callable[[], Awaitable[None]]] = session.info.pop(POST_COMMIT_TASKS_KEY, [])
    for task_factory in tasks:
        try:
            await task_factory()
        except Exception:
            logger.exception("Post-commit task failed")


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
            await run_post_commit_tasks(session)
        except Exception:
            session.info.pop(POST_COMMIT_TASKS_KEY, None)
            await session.rollback()
            raise

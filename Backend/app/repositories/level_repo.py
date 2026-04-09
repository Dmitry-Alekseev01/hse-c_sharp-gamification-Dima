# app/repositories/level_repo.py
from sqlalchemy import select
from app.models.level import Level

async def list_levels(session):
    q = select(Level).order_by(Level.required_points)
    res = await session.execute(q)
    return res.scalars().all()

async def get_current_level_for_points(session, points: int):
    # get highest level where required_points <= points
    q = select(Level).where(Level.required_points <= points).order_by(Level.required_points.desc()).limit(1)
    res = await session.execute(q)
    return res.scalars().first()


async def get_level_by_id(session, level_id: int):
    q = select(Level).where(Level.id == level_id).limit(1)
    res = await session.execute(q)
    return res.scalars().first()


async def get_next_level_for_points(session, points: float):
    q = select(Level).where(Level.required_points > points).order_by(Level.required_points.asc()).limit(1)
    res = await session.execute(q)
    return res.scalars().first()

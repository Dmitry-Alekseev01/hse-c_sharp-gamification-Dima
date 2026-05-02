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


async def get_level_by_name(session, name: str):
    q = select(Level).where(Level.name == name).limit(1)
    res = await session.execute(q)
    return res.scalars().first()


async def get_level_by_required_points(session, required_points: int):
    q = select(Level).where(Level.required_points == required_points).limit(1)
    res = await session.execute(q)
    return res.scalars().first()


async def create_level(
    session,
    *,
    name: str,
    required_points: int,
    description: str | None = None,
):
    level = Level(
        name=name,
        required_points=required_points,
        description=description,
    )
    session.add(level)
    await session.flush()
    await session.refresh(level)
    return level


async def update_level(
    session,
    level_id: int,
    *,
    name: str | None = None,
    required_points: int | None = None,
    description: str | None = None,
):
    level = await get_level_by_id(session, level_id)
    if level is None:
        return None
    if name is not None:
        level.name = name
    if required_points is not None:
        level.required_points = required_points
    if description is not None:
        level.description = description
    await session.flush()
    await session.refresh(level)
    return level


async def delete_level(session, level_id: int) -> bool:
    level = await get_level_by_id(session, level_id)
    if level is None:
        return False
    await session.delete(level)
    await session.flush()
    return True

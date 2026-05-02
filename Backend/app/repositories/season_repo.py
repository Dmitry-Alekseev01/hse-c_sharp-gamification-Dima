from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.season import Season


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def create_season(
    session: AsyncSession,
    *,
    code: str,
    title: str,
    starts_at: datetime,
    ends_at: datetime,
    is_active: bool = True,
    created_by: int | None = None,
) -> Season:
    season = Season(
        code=code,
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        is_active=is_active,
        created_by=created_by,
        created_at=utcnow_naive(),
        updated_at=utcnow_naive(),
    )
    session.add(season)
    await session.flush()
    return season


async def get_season(session: AsyncSession, season_id: int) -> Season | None:
    return await session.get(Season, season_id)


async def get_season_by_code(session: AsyncSession, code: str) -> Season | None:
    stmt = select(Season).where(Season.code == code).limit(1)
    return (await session.execute(stmt)).scalars().first()


async def update_season(
    session: AsyncSession,
    season_id: int,
    **changes,
) -> Season | None:
    season = await get_season(session, season_id)
    if season is None:
        return None

    if "code" in changes:
        season.code = changes["code"]
    if "title" in changes:
        season.title = changes["title"]
    if "starts_at" in changes:
        season.starts_at = changes["starts_at"]
    if "ends_at" in changes:
        season.ends_at = changes["ends_at"]
    if "is_active" in changes:
        season.is_active = changes["is_active"]

    season.updated_at = utcnow_naive()
    await session.flush()
    await session.refresh(season)
    return season


async def delete_season(session: AsyncSession, season_id: int) -> bool:
    season = await get_season(session, season_id)
    if season is None:
        return False
    await session.delete(season)
    await session.flush()
    return True


async def list_seasons(
    session: AsyncSession,
    *,
    only_active: bool = False,
) -> list[Season]:
    stmt = select(Season)
    if only_active:
        now = utcnow_naive()
        stmt = stmt.where(
            Season.is_active.is_(True),
            or_(Season.starts_at.is_(None), Season.starts_at <= now),
            or_(Season.ends_at.is_(None), Season.ends_at >= now),
        )
    stmt = stmt.order_by(Season.starts_at.desc(), Season.id.desc())
    return list((await session.execute(stmt)).scalars().all())

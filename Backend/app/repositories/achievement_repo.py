from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement_definition import AchievementDefinition


async def create_achievement_definition(
    session: AsyncSession,
    *,
    code: str,
    title: str,
    description: str,
    reward: str | None,
    criteria_type: str,
    threshold_value: int,
    is_active: bool,
) -> AchievementDefinition:
    definition = AchievementDefinition(
        code=code,
        title=title,
        description=description,
        reward=reward,
        criteria_type=criteria_type,
        threshold_value=threshold_value,
        is_active=is_active,
    )
    session.add(definition)
    await session.flush()
    return definition


async def list_achievement_definitions(
    session: AsyncSession,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[AchievementDefinition]:
    stmt = (
        select(AchievementDefinition)
        .order_by(AchievementDefinition.threshold_value.asc(), AchievementDefinition.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_achievement_definition(session: AsyncSession, achievement_definition_id: int) -> AchievementDefinition | None:
    return await session.get(AchievementDefinition, achievement_definition_id)


async def get_achievement_definition_by_code(session: AsyncSession, code: str) -> AchievementDefinition | None:
    stmt = select(AchievementDefinition).where(AchievementDefinition.code == code).limit(1)
    return (await session.execute(stmt)).scalars().first()


async def update_achievement_definition(
    session: AsyncSession,
    achievement_definition_id: int,
    **changes,
) -> AchievementDefinition | None:
    definition = await get_achievement_definition(session, achievement_definition_id)
    if definition is None:
        return None

    if "code" in changes:
        definition.code = changes["code"]
    if "title" in changes:
        definition.title = changes["title"]
    if "description" in changes:
        definition.description = changes["description"]
    if "reward" in changes:
        definition.reward = changes["reward"]
    if "criteria_type" in changes:
        definition.criteria_type = changes["criteria_type"]
    if "threshold_value" in changes:
        definition.threshold_value = changes["threshold_value"]
    if "is_active" in changes:
        definition.is_active = changes["is_active"]

    await session.flush()
    await session.refresh(definition)
    return definition


async def delete_achievement_definition(session: AsyncSession, achievement_definition_id: int) -> bool:
    definition = await get_achievement_definition(session, achievement_definition_id)
    if definition is None:
        return False
    await session.delete(definition)
    await session.flush()
    return True

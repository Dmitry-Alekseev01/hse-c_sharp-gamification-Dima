from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward_definition import RewardDefinition
from app.models.unlock_rule import UnlockRule


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def create_reward_definition(
    session: AsyncSession,
    *,
    code: str,
    title: str,
    description: str | None,
    reward_type: str,
    payload_json: dict[str, object] | None,
    is_active: bool,
) -> RewardDefinition:
    now = utcnow_naive()
    reward_definition = RewardDefinition(
        code=code,
        title=title,
        description=description,
        reward_type=reward_type,
        payload_json=payload_json,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(reward_definition)
    await session.flush()
    return reward_definition


async def list_reward_definitions(
    session: AsyncSession,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[RewardDefinition]:
    stmt = select(RewardDefinition).order_by(RewardDefinition.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_reward_definition(session: AsyncSession, reward_definition_id: int) -> RewardDefinition | None:
    return await session.get(RewardDefinition, reward_definition_id)


async def get_reward_definition_by_code(session: AsyncSession, code: str) -> RewardDefinition | None:
    stmt = select(RewardDefinition).where(RewardDefinition.code == code).limit(1)
    return (await session.execute(stmt)).scalars().first()


async def update_reward_definition(
    session: AsyncSession,
    reward_definition_id: int,
    **changes,
) -> RewardDefinition | None:
    reward_definition = await get_reward_definition(session, reward_definition_id)
    if reward_definition is None:
        return None

    if "code" in changes:
        reward_definition.code = changes["code"]
    if "title" in changes:
        reward_definition.title = changes["title"]
    if "description" in changes:
        reward_definition.description = changes["description"]
    if "reward_type" in changes:
        reward_definition.reward_type = changes["reward_type"]
    if "payload_json" in changes:
        reward_definition.payload_json = changes["payload_json"]
    if "is_active" in changes:
        reward_definition.is_active = changes["is_active"]

    reward_definition.updated_at = utcnow_naive()
    await session.flush()
    await session.refresh(reward_definition)
    return reward_definition


async def delete_reward_definition(session: AsyncSession, reward_definition_id: int) -> bool:
    reward_definition = await get_reward_definition(session, reward_definition_id)
    if reward_definition is None:
        return False
    await session.delete(reward_definition)
    await session.flush()
    return True


async def create_unlock_rule(
    session: AsyncSession,
    *,
    reward_definition_id: int,
    source_type: str,
    source_code: str | None,
    min_level_required: int | None,
    is_active: bool,
) -> UnlockRule:
    now = utcnow_naive()
    unlock_rule = UnlockRule(
        reward_definition_id=reward_definition_id,
        source_type=source_type,
        source_code=source_code,
        min_level_required=min_level_required,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(unlock_rule)
    await session.flush()
    return unlock_rule


async def list_unlock_rules(
    session: AsyncSession,
    *,
    reward_definition_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[UnlockRule]:
    stmt = select(UnlockRule)
    if reward_definition_id is not None:
        stmt = stmt.where(UnlockRule.reward_definition_id == reward_definition_id)
    stmt = stmt.order_by(UnlockRule.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_unlock_rule(session: AsyncSession, unlock_rule_id: int) -> UnlockRule | None:
    return await session.get(UnlockRule, unlock_rule_id)


async def update_unlock_rule(
    session: AsyncSession,
    unlock_rule_id: int,
    **changes,
) -> UnlockRule | None:
    unlock_rule = await get_unlock_rule(session, unlock_rule_id)
    if unlock_rule is None:
        return None

    if "reward_definition_id" in changes:
        unlock_rule.reward_definition_id = changes["reward_definition_id"]
    if "source_type" in changes:
        unlock_rule.source_type = changes["source_type"]
    if "source_code" in changes:
        unlock_rule.source_code = changes["source_code"]
    if "min_level_required" in changes:
        unlock_rule.min_level_required = changes["min_level_required"]
    if "is_active" in changes:
        unlock_rule.is_active = changes["is_active"]

    unlock_rule.updated_at = utcnow_naive()
    await session.flush()
    await session.refresh(unlock_rule)
    return unlock_rule


async def delete_unlock_rule(session: AsyncSession, unlock_rule_id: int) -> bool:
    unlock_rule = await get_unlock_rule(session, unlock_rule_id)
    if unlock_rule is None:
        return False
    await session.delete(unlock_rule)
    await session.flush()
    return True

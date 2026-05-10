from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement_definition import AchievementDefinition
from app.models.analytics import Analytics
from app.models.challenge import Challenge, UserChallengeClaim
from app.models.reward_definition import RewardDefinition
from app.models.unlock_rule import UnlockRule
from app.models.user_achievement import UserAchievement
from app.models.user_reward import UserReward

# Rewards are cosmetic/profile entities only.
# They do not control access to tests, materials, or levels.
# Access control is handled by level thresholds and dedicated access logic.


DEFAULT_REWARD_DEFINITIONS: list[dict[str, Any]] = [
    {
        "code": "reward_first_steps_badge",
        "title": "First Steps Badge",
        "description": "Awarded for completing the very first achievement milestone.",
        "reward_type": "badge",
        "payload_json": {"icon": "first_steps", "rarity": "common"},
    },
    {
        "code": "reward_challenge_finisher",
        "title": "Challenge Finisher",
        "description": "Awarded for claiming at least one challenge reward.",
        "reward_type": "badge",
        "payload_json": {"icon": "challenge_finisher", "rarity": "rare"},
    },
    {
        "code": "reward_level_2_unlock",
        "title": "Level 2 Milestone Badge",
        "description": "Cosmetic badge for reaching the intermediate points milestone.",
        "reward_type": "badge",
        "payload_json": {"tier": "intermediate", "category": "milestone"},
    },
    {
        "code": "reward_level_3_unlock",
        "title": "Level 3 Milestone Badge",
        "description": "Cosmetic badge for reaching the advanced points milestone.",
        "reward_type": "badge",
        "payload_json": {"tier": "advanced", "category": "milestone"},
    },
]


DEFAULT_UNLOCK_RULES: list[dict[str, Any]] = [
    {
        "reward_code": "reward_first_steps_badge",
        "source_type": "achievement",
        "source_code": "first_steps",
        "min_level_required": None,
    },
    {
        "reward_code": "reward_challenge_finisher",
        "source_type": "challenge",
        "source_code": None,
        "min_level_required": None,
    },
    {
        "reward_code": "reward_level_2_unlock",
        "source_type": "level",
        "source_code": None,
        "min_level_required": 60,
    },
    {
        "reward_code": "reward_level_3_unlock",
        "source_type": "level",
        "source_code": None,
        "min_level_required": 140,
    },
]


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _ensure_default_rewards_and_rules(session: AsyncSession) -> None:
    reward_by_code: dict[str, RewardDefinition] = {}
    for spec in DEFAULT_REWARD_DEFINITIONS:
        existing = (
            await session.execute(select(RewardDefinition).where(RewardDefinition.code == spec["code"]))
        ).scalars().first()
        if existing is None:
            existing = RewardDefinition(
                code=spec["code"],
                title=spec["title"],
                description=spec["description"],
                reward_type=spec["reward_type"],
                payload_json=spec["payload_json"],
                is_active=True,
            )
            session.add(existing)
        else:
            existing.title = spec["title"]
            existing.description = spec["description"]
            existing.reward_type = spec["reward_type"]
            existing.payload_json = spec["payload_json"]
            existing.is_active = True
        reward_by_code[spec["code"]] = existing
    await session.flush()

    for rule_spec in DEFAULT_UNLOCK_RULES:
        reward = reward_by_code[rule_spec["reward_code"]]
        existing_rule = (
            await session.execute(
                select(UnlockRule).where(
                    UnlockRule.reward_definition_id == reward.id,
                    UnlockRule.source_type == rule_spec["source_type"],
                    UnlockRule.source_code == rule_spec["source_code"],
                    UnlockRule.min_level_required == rule_spec["min_level_required"],
                )
            )
        ).scalars().first()
        if existing_rule is None:
            session.add(
                UnlockRule(
                    reward_definition_id=reward.id,
                    source_type=rule_spec["source_type"],
                    source_code=rule_spec["source_code"],
                    min_level_required=rule_spec["min_level_required"],
                    is_active=True,
                )
            )
        else:
            existing_rule.is_active = True
    await session.flush()


async def _collect_reward_context(session: AsyncSession, user_id: int) -> dict[str, Any]:
    achievement_codes = set(
        (
            await session.execute(
                select(AchievementDefinition.code)
                .join(UserAchievement, UserAchievement.achievement_id == AchievementDefinition.id)
                .where(UserAchievement.user_id == user_id)
            )
        ).scalars().all()
    )
    challenge_codes = set(
        (
            await session.execute(
                select(Challenge.code)
                .join(UserChallengeClaim, UserChallengeClaim.challenge_id == Challenge.id)
                .where(UserChallengeClaim.user_id == user_id)
            )
        ).scalars().all()
    )
    analytics = (
        await session.execute(select(Analytics).where(Analytics.user_id == user_id))
    ).scalars().first()
    total_points = float(analytics.total_points or 0.0) if analytics is not None else 0.0
    return {
        "achievement_codes": achievement_codes,
        "challenge_codes": challenge_codes,
        "total_points": total_points,
    }


def _is_rule_reward_eligible(rule: UnlockRule, ctx: dict[str, Any]) -> bool:
    source_type = str(rule.source_type)
    source_code = rule.source_code
    min_level_required = int(rule.min_level_required or 0)
    total_points = float(ctx["total_points"])

    eligible = False
    if source_type == "achievement":
        codes = ctx["achievement_codes"]
        eligible = bool(codes) if source_code is None else source_code in codes
    elif source_type == "challenge":
        codes = ctx["challenge_codes"]
        eligible = bool(codes) if source_code is None else source_code in codes
    elif source_type == "level":
        # "level" source is treated as a points milestone only for cosmetic rewards.
        eligible = total_points >= float(min_level_required)

    if source_type in {"achievement", "challenge"} and min_level_required > 0:
        eligible = eligible and total_points >= float(min_level_required)
    return bool(eligible)


async def sync_user_rewards(session: AsyncSession, user_id: int) -> int:
    await _ensure_default_rewards_and_rules(session)
    ctx = await _collect_reward_context(session, user_id)
    rules = (
        await session.execute(
            select(UnlockRule).where(UnlockRule.is_active.is_(True)).order_by(UnlockRule.id.asc())
        )
    ).scalars().all()
    existing_rewards = set(
        (
            await session.execute(
                select(UserReward.reward_definition_id).where(UserReward.user_id == user_id)
            )
        ).scalars().all()
    )

    granted = 0
    now = utcnow_naive()
    for rule in rules:
        reward_id = int(rule.reward_definition_id)
        if reward_id in existing_rewards:
            continue
        if not _is_rule_reward_eligible(rule, ctx):
            continue
        session.add(
            UserReward(
                user_id=user_id,
                reward_definition_id=reward_id,
                source_type=str(rule.source_type),
                source_ref=rule.source_code or (str(rule.min_level_required) if rule.min_level_required else None),
                earned_at=now,
            )
        )
        existing_rewards.add(reward_id)
        granted += 1
    await session.flush()
    return granted


async def list_user_rewards(session: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(UserReward, RewardDefinition)
            .join(RewardDefinition, RewardDefinition.id == UserReward.reward_definition_id)
            .where(UserReward.user_id == user_id)
            .order_by(UserReward.earned_at.desc(), UserReward.id.desc())
        )
    ).all()
    return [
        {
            "id": reward.id,
            "code": definition.code,
            "title": definition.title,
            "description": definition.description,
            "reward_type": definition.reward_type,
            "payload": definition.payload_json or {},
            "source_type": reward.source_type,
            "source_ref": reward.source_ref,
            "earned_at": reward.earned_at,
        }
        for reward, definition in rows
    ]


async def list_user_unlocks(session: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    # Backward-compatible endpoint name. It returns reward condition status only,
    # and does not represent API/content access permissions.
    ctx = await _collect_reward_context(session, user_id)
    rows = (
        await session.execute(
            select(UnlockRule, RewardDefinition)
            .join(RewardDefinition, RewardDefinition.id == UnlockRule.reward_definition_id)
            .where(UnlockRule.is_active.is_(True), RewardDefinition.is_active.is_(True))
            .order_by(RewardDefinition.code.asc(), UnlockRule.id.asc())
        )
    ).all()
    user_rewards = {
        row.reward_definition_id: row
        for row in (
            await session.execute(select(UserReward).where(UserReward.user_id == user_id))
        ).scalars().all()
    }
    items: list[dict[str, Any]] = []
    for rule, definition in rows:
        granted = user_rewards.get(definition.id)
        items.append(
            {
                "reward_code": definition.code,
                "reward_title": definition.title,
                "source_type": rule.source_type,
                "source_code": rule.source_code,
                "min_level_required": rule.min_level_required,
                "is_eligible": _is_rule_reward_eligible(rule, ctx),
                "is_unlocked": granted is not None,
                "earned_at": granted.earned_at if granted is not None else None,
            }
        )
    return items

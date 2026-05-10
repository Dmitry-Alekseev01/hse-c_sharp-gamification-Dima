import pytest
from datetime import UTC, datetime

from sqlalchemy import select

from app.models.achievement_definition import AchievementDefinition
from app.models.analytics import Analytics
from app.models.challenge import Challenge, UserChallengeClaim
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.services import reward_service

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_sync_user_rewards_grants_achievement_and_level_rewards(db):
    user = User(username="reward_user@example.com", password_hash="x", role="user")
    db.add(user)
    await db.flush()

    achievement = (
        await db.execute(
            select(AchievementDefinition).where(AchievementDefinition.code == "first_steps")
        )
    ).scalars().first()
    if achievement is None:
        achievement = AchievementDefinition(
            code="first_steps",
            title="First Steps",
            description="Complete first attempt",
            reward="badge",
            criteria_type="completed_attempts",
            threshold_value=1,
            is_active=True,
        )
        db.add(achievement)
        await db.flush()

    db.add(UserAchievement(user_id=user.id, achievement_id=achievement.id, source_event="unit_test"))
    db.add(
        Analytics(
            user_id=user.id,
            total_points=150.0,
            tests_taken=3,
            streak_days=4,
            current_level_id=None,
        )
    )
    await db.flush()

    granted_count = await reward_service.sync_user_rewards(db, user.id)
    assert granted_count >= 3

    rewards = await reward_service.list_user_rewards(db, user.id)
    reward_codes = {item["code"] for item in rewards}
    assert "reward_first_steps_badge" in reward_codes
    assert "reward_level_2_unlock" in reward_codes
    assert "reward_level_3_unlock" in reward_codes
    level_rewards = [item for item in rewards if item["code"] in {"reward_level_2_unlock", "reward_level_3_unlock"}]
    assert level_rewards
    assert all(item["reward_type"] == "badge" for item in level_rewards)


@pytest.mark.asyncio
async def test_sync_user_rewards_grants_challenge_reward_from_claim(db):
    user = User(username="reward_challenge_user@example.com", password_hash="x", role="user")
    db.add(user)
    await db.flush()

    challenge = Challenge(
        code="challenge_reward_case",
        title="Challenge Reward Case",
        description=None,
        period_type="daily",
        event_type="answer_submitted",
        target_value=1,
        reward_points=10.0,
        is_active=True,
        starts_at=None,
        ends_at=None,
        created_by=None,
    )
    db.add(challenge)
    await db.flush()

    db.add(
        UserChallengeClaim(
            user_id=user.id,
            challenge_id=challenge.id,
            period_key="2026-04-22",
            reward_points=10.0,
            ledger_entry_id=None,
            claimed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await db.flush()

    await reward_service.sync_user_rewards(db, user.id)
    unlocks = await reward_service.list_user_unlocks(db, user.id)
    challenge_unlock = next(item for item in unlocks if item["reward_code"] == "reward_challenge_finisher")
    assert challenge_unlock["is_eligible"] is True
    assert challenge_unlock["is_unlocked"] is True


@pytest.mark.asyncio
async def test_reward_read_paths_do_not_trigger_sync_side_effects(db, monkeypatch):
    user = User(username="reward_read_only_user@example.com", password_hash="x", role="user")
    db.add(user)
    await db.flush()

    async def _fail_if_sync_called(session, user_id: int):
        del session, user_id
        raise AssertionError("sync_user_rewards must not be called from read-path")

    monkeypatch.setattr(reward_service, "sync_user_rewards", _fail_if_sync_called)

    rewards = await reward_service.list_user_rewards(db, user.id)
    unlocks = await reward_service.list_user_unlocks(db, user.id)

    assert isinstance(rewards, list)
    assert isinstance(unlocks, list)

# tests/unit/test_analytics_repo.py
import pytest
pytestmark = pytest.mark.asyncio
from datetime import datetime, timedelta

from app.models.level import Level
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt as AttemptModel
from app.models.user import User
from app.repositories import analytics_repo

@pytest.mark.asyncio
async def test_create_or_update_analytics_and_leaderboard(db):
    # create two users
    u1 = User(username="a", password_hash="x", full_name="A", role="user")
    u2 = User(username="b", password_hash="x", full_name="B", role="user")
    db.add_all([u1, u2])
    await db.flush()

    # add points
    a1 = await analytics_repo.create_or_update_analytics(db, u1.id, points_delta=10.0, mark_active=True)
    a2 = await analytics_repo.create_or_update_analytics(db, u2.id, points_delta=5.0, mark_active=True)

    assert a1.total_points >= 10.0
    assert a2.total_points >= 5.0

    lb = await analytics_repo.get_leaderboard(db, limit=10)
    assert isinstance(lb, list)
    # first entry should be present u1 (10 points)
    assert any(entry["user_id"] == u1.id for entry in lb)
    # ordering by total_points desc (if at least 2 rows)
    if len(lb) >= 2:
        assert lb[0]["total_points"] >= lb[1]["total_points"]


@pytest.mark.asyncio
async def test_tests_taken_changes_only_for_completed_attempts(db):
    user = User(username="analytics_user", password_hash="x", full_name="Analytics", role="user")
    db.add(user)
    await db.flush()

    analytics = await analytics_repo.create_or_update_analytics(db, user.id, points_delta=12.0, mark_active=True)
    assert analytics.total_points == pytest.approx(12.0)
    assert analytics.tests_taken == 0

    analytics = await analytics_repo.register_completed_attempt(db, user.id)
    assert analytics.tests_taken == 1

    analytics = await analytics_repo.register_completed_attempt(db, user.id)
    assert analytics.tests_taken == 2


@pytest.mark.asyncio
async def test_analytics_updates_streak_and_level(db):
    user = User(username="gamified_user", password_hash="x", full_name="Gamified", role="user")
    level_1 = Level(name="Beginner", required_points=0)
    level_2 = Level(name="Advanced", required_points=50)
    db.add_all([user, level_1, level_2])
    await db.flush()

    analytics = await analytics_repo.create_or_update_analytics(db, user.id, points_delta=10.0, mark_active=True)
    assert analytics.streak_days == 1
    assert analytics.current_level_id == level_1.id

    analytics.last_active = datetime.utcnow() - timedelta(days=1)
    await db.flush()

    analytics = await analytics_repo.create_or_update_analytics(db, user.id, points_delta=45.0, mark_active=True)
    assert analytics.streak_days == 2
    assert analytics.current_level_id == level_2.id


@pytest.mark.asyncio
async def test_gamification_progress_reports_next_level(db):
    user = User(username="progress_user", password_hash="x", role="user")
    level_1 = Level(name="Beginner", required_points=0)
    level_2 = Level(name="Intermediate", required_points=100)
    db.add_all([user, level_1, level_2])
    await db.flush()

    await analytics_repo.create_or_update_analytics(db, user.id, points_delta=40.0, mark_active=True)
    progress = await analytics_repo.get_gamification_progress(db, user.id)

    assert progress is not None
    assert progress["current_level"]["id"] == level_1.id
    assert progress["next_level"]["id"] == level_2.id
    assert progress["points_to_next_level"] == pytest.approx(60.0)
    assert progress["completed_attempts"] == 0
    assert progress["earned_badges_count"] >= 0
    assert any(badge["code"] == "first_steps" and badge["earned"] is False for badge in progress["badges"])


@pytest.mark.asyncio
async def test_gamification_progress_reports_earned_badges(db):
    user = User(username="badge_user", password_hash="x", role="user")
    level_1 = Level(name="Beginner", required_points=0)
    test = Test(title="Badge test", published=True)
    db.add_all([user, level_1, test])
    await db.flush()

    analytics = await analytics_repo.create_or_update_analytics(db, user.id, points_delta=120.0, mark_active=True)
    analytics.streak_days = 7
    db.add(
        AttemptModel(
            user_id=user.id,
            test_id=test.id,
            status="completed",
            score=10.0,
            max_score=10.0,
            time_spent_seconds=60,
            submitted_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
    )
    await db.flush()
    await analytics_repo.register_completed_attempt(db, user.id)

    progress = await analytics_repo.get_gamification_progress(db, user.id)

    assert progress is not None
    assert progress["completed_attempts"] == 1
    earned = {badge["code"] for badge in progress["badges"] if badge["earned"]}
    assert "first_steps" in earned
    assert "focused_three" in earned
    assert "focused_week" in earned
    assert "century_points" in earned

# tests/unit/test_analytics_repo.py
import pytest
pytestmark = pytest.mark.asyncio
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
    assert any(entry["id"] == u1.id for entry in lb)
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

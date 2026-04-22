import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.repositories import analytics_repo

pytestmark = pytest.mark.asyncio


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client, username: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def test_rewards_and_unlocks_api(client, db):
    user = User(
        username="reward_student@example.com",
        password_hash=get_password_hash("stud123"),
        role="user",
        full_name="Reward Student",
    )
    db.add(user)
    await db.flush()

    await analytics_repo.apply_points_delta(
        db,
        user.id,
        80.0,
        reason_code="seed_points_reward",
        source_type="seed",
        source_id=1,
        idempotency_key="seed_points_reward",
    )
    await db.flush()

    token = await login(client, user.username, "stud123")

    rewards_response = await client.get("/api/v1/analytics/me/rewards", headers=auth_headers(token))
    assert rewards_response.status_code == 200, rewards_response.text
    rewards_payload = rewards_response.json()
    assert isinstance(rewards_payload, list)
    level_2_reward = next(item for item in rewards_payload if item["code"] == "reward_level_2_unlock")
    assert level_2_reward["reward_type"] == "badge"

    unlocks_response = await client.get("/api/v1/analytics/me/unlocks", headers=auth_headers(token))
    assert unlocks_response.status_code == 200, unlocks_response.text
    unlocks_payload = unlocks_response.json()
    assert isinstance(unlocks_payload, list)
    level_2_unlock = next(item for item in unlocks_payload if item["reward_code"] == "reward_level_2_unlock")
    assert level_2_unlock["is_eligible"] is True
    assert level_2_unlock["is_unlocked"] is True

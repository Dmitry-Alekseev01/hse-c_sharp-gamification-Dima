from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import get_password_hash
from app.models.user import User

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


async def seed_user(db, *, username: str, password: str, role: str, full_name: str) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
        full_name=full_name,
    )
    db.add(user)
    await db.flush()
    return user


async def test_challenge_admin_full_crud(client, db):
    admin = await seed_user(
        db,
        username="challenge_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Challenge Admin",
    )
    teacher = await seed_user(
        db,
        username="challenge_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Challenge Teacher",
    )

    admin_token = await login(client, admin.username, "admin123")
    teacher_token = await login(client, teacher.username, "teach123")

    create_response = await client.post(
        "/api/v1/analytics/challenges",
        headers=auth_headers(admin_token),
        json={
            "code": "challenge_crud",
            "title": "Challenge CRUD",
            "description": "CRUD challenge",
            "period_type": "daily",
            "event_type": "answer_submitted",
            "target_value": 2,
            "reward_points": 25.0,
            "is_active": True,
        },
    )
    assert create_response.status_code == 201, create_response.text
    challenge_id = create_response.json()["id"]

    list_response = await client.get(
        "/api/v1/analytics/challenges?limit=100&offset=0",
        headers=auth_headers(admin_token),
    )
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == challenge_id for item in list_response.json())

    get_response = await client.get(
        f"/api/v1/analytics/challenges/{challenge_id}",
        headers=auth_headers(admin_token),
    )
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["code"] == "challenge_crud"

    forbidden_get_response = await client.get(
        f"/api/v1/analytics/challenges/{challenge_id}",
        headers=auth_headers(teacher_token),
    )
    assert forbidden_get_response.status_code == 403, forbidden_get_response.text

    update_response = await client.patch(
        f"/api/v1/analytics/challenges/{challenge_id}",
        headers=auth_headers(admin_token),
        json={
            "title": "Challenge Updated",
            "reward_points": 30.0,
            "is_active": False,
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["title"] == "Challenge Updated"
    assert update_response.json()["reward_points"] == pytest.approx(30.0)
    assert update_response.json()["is_active"] is False

    forbidden_update_response = await client.patch(
        f"/api/v1/analytics/challenges/{challenge_id}",
        headers=auth_headers(teacher_token),
        json={"title": "Forbidden"},
    )
    assert forbidden_update_response.status_code == 403, forbidden_update_response.text

    delete_response = await client.delete(
        f"/api/v1/analytics/challenges/{challenge_id}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204, delete_response.text

    not_found_response = await client.get(
        f"/api/v1/analytics/challenges/{challenge_id}",
        headers=auth_headers(admin_token),
    )
    assert not_found_response.status_code == 404, not_found_response.text


async def test_season_admin_full_crud(client, db):
    admin = await seed_user(
        db,
        username="season_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Season Admin",
    )
    user = await seed_user(
        db,
        username="season_user@example.com",
        password="user123",
        role="user",
        full_name="Season User",
    )

    admin_token = await login(client, admin.username, "admin123")
    user_token = await login(client, user.username, "user123")

    create_response = await client.post(
        "/api/v1/analytics/seasons",
        headers=auth_headers(admin_token),
        json={
            "code": "season_crud",
            "title": "Season CRUD",
            "starts_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "ends_at": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
            "is_active": True,
        },
    )
    assert create_response.status_code == 201, create_response.text
    season_id = create_response.json()["id"]

    user_get_response = await client.get(
        f"/api/v1/analytics/seasons/{season_id}",
        headers=auth_headers(user_token),
    )
    assert user_get_response.status_code == 200, user_get_response.text
    assert user_get_response.json()["code"] == "season_crud"

    forbidden_update_response = await client.patch(
        f"/api/v1/analytics/seasons/{season_id}",
        headers=auth_headers(user_token),
        json={"title": "Forbidden"},
    )
    assert forbidden_update_response.status_code == 403, forbidden_update_response.text

    update_response = await client.patch(
        f"/api/v1/analytics/seasons/{season_id}",
        headers=auth_headers(admin_token),
        json={
            "title": "Season Updated",
            "code": "season_crud_updated",
            "ends_at": (datetime.now(UTC) + timedelta(days=20)).isoformat(),
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["title"] == "Season Updated"
    assert update_response.json()["code"] == "season_crud_updated"

    delete_response = await client.delete(
        f"/api/v1/analytics/seasons/{season_id}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204, delete_response.text

    not_found_response = await client.get(
        f"/api/v1/analytics/seasons/{season_id}",
        headers=auth_headers(admin_token),
    )
    assert not_found_response.status_code == 404, not_found_response.text


async def test_reward_definition_admin_full_crud(client, db):
    admin = await seed_user(
        db,
        username="reward_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Reward Admin",
    )
    teacher = await seed_user(
        db,
        username="reward_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Reward Teacher",
    )

    admin_token = await login(client, admin.username, "admin123")
    teacher_token = await login(client, teacher.username, "teach123")

    forbidden_create_response = await client.post(
        "/api/v1/analytics/reward-definitions",
        headers=auth_headers(teacher_token),
        json={
            "code": "reward_forbidden",
            "title": "Forbidden Reward",
            "reward_type": "badge",
        },
    )
    assert forbidden_create_response.status_code == 403, forbidden_create_response.text

    create_response = await client.post(
        "/api/v1/analytics/reward-definitions",
        headers=auth_headers(admin_token),
        json={
            "code": "reward_crud_badge",
            "title": "Reward CRUD Badge",
            "description": "Created in CRUD integration test",
            "reward_type": "badge",
            "payload_json": {"icon": "star"},
            "is_active": True,
        },
    )
    assert create_response.status_code == 201, create_response.text
    reward_definition_id = create_response.json()["id"]

    duplicate_response = await client.post(
        "/api/v1/analytics/reward-definitions",
        headers=auth_headers(admin_token),
        json={
            "code": "reward_crud_badge",
            "title": "Duplicate",
            "reward_type": "badge",
        },
    )
    assert duplicate_response.status_code == 400, duplicate_response.text

    list_response = await client.get(
        "/api/v1/analytics/reward-definitions?limit=100&offset=0",
        headers=auth_headers(admin_token),
    )
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == reward_definition_id for item in list_response.json())

    get_response = await client.get(
        f"/api/v1/analytics/reward-definitions/{reward_definition_id}",
        headers=auth_headers(admin_token),
    )
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["code"] == "reward_crud_badge"

    update_response = await client.patch(
        f"/api/v1/analytics/reward-definitions/{reward_definition_id}",
        headers=auth_headers(admin_token),
        json={
            "title": "Reward CRUD Badge Updated",
            "is_active": False,
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["title"] == "Reward CRUD Badge Updated"
    assert update_response.json()["is_active"] is False

    delete_response = await client.delete(
        f"/api/v1/analytics/reward-definitions/{reward_definition_id}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204, delete_response.text

    not_found_response = await client.get(
        f"/api/v1/analytics/reward-definitions/{reward_definition_id}",
        headers=auth_headers(admin_token),
    )
    assert not_found_response.status_code == 404, not_found_response.text


async def test_unlock_rule_admin_full_crud(client, db):
    admin = await seed_user(
        db,
        username="unlock_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Unlock Admin",
    )
    user = await seed_user(
        db,
        username="unlock_user@example.com",
        password="user123",
        role="user",
        full_name="Unlock User",
    )

    admin_token = await login(client, admin.username, "admin123")
    user_token = await login(client, user.username, "user123")

    create_reward_response = await client.post(
        "/api/v1/analytics/reward-definitions",
        headers=auth_headers(admin_token),
        json={
            "code": "reward_for_unlock_crud",
            "title": "Unlock Reward",
            "reward_type": "badge",
            "is_active": True,
        },
    )
    assert create_reward_response.status_code == 201, create_reward_response.text
    reward_definition_id = create_reward_response.json()["id"]

    invalid_level_rule_response = await client.post(
        "/api/v1/analytics/unlock-rules",
        headers=auth_headers(admin_token),
        json={
            "reward_definition_id": reward_definition_id,
            "source_type": "level",
            "is_active": True,
        },
    )
    assert invalid_level_rule_response.status_code == 400, invalid_level_rule_response.text

    create_rule_response = await client.post(
        "/api/v1/analytics/unlock-rules",
        headers=auth_headers(admin_token),
        json={
            "reward_definition_id": reward_definition_id,
            "source_type": "level",
            "min_level_required": 50,
            "is_active": True,
        },
    )
    assert create_rule_response.status_code == 201, create_rule_response.text
    unlock_rule_id = create_rule_response.json()["id"]

    forbidden_get_response = await client.get(
        f"/api/v1/analytics/unlock-rules/{unlock_rule_id}",
        headers=auth_headers(user_token),
    )
    assert forbidden_get_response.status_code == 403, forbidden_get_response.text

    list_response = await client.get(
        f"/api/v1/analytics/unlock-rules?reward_definition_id={reward_definition_id}&limit=100&offset=0",
        headers=auth_headers(admin_token),
    )
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == unlock_rule_id for item in list_response.json())

    update_rule_response = await client.patch(
        f"/api/v1/analytics/unlock-rules/{unlock_rule_id}",
        headers=auth_headers(admin_token),
        json={
            "source_type": "challenge",
            "source_code": "weekly_finish",
            "min_level_required": None,
            "is_active": False,
        },
    )
    assert update_rule_response.status_code == 200, update_rule_response.text
    assert update_rule_response.json()["source_type"] == "challenge"
    assert update_rule_response.json()["source_code"] == "weekly_finish"
    assert update_rule_response.json()["is_active"] is False

    delete_rule_response = await client.delete(
        f"/api/v1/analytics/unlock-rules/{unlock_rule_id}",
        headers=auth_headers(admin_token),
    )
    assert delete_rule_response.status_code == 204, delete_rule_response.text

    not_found_rule_response = await client.get(
        f"/api/v1/analytics/unlock-rules/{unlock_rule_id}",
        headers=auth_headers(admin_token),
    )
    assert not_found_rule_response.status_code == 404, not_found_rule_response.text


async def test_level_admin_full_crud(client, db):
    admin = await seed_user(
        db,
        username="level_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Level Admin",
    )
    teacher = await seed_user(
        db,
        username="level_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Level Teacher",
    )

    admin_token = await login(client, admin.username, "admin123")
    teacher_token = await login(client, teacher.username, "teach123")

    forbidden_create_response = await client.post(
        "/api/v1/analytics/levels",
        headers=auth_headers(teacher_token),
        json={"name": "Forbidden", "required_points": 10},
    )
    assert forbidden_create_response.status_code == 403, forbidden_create_response.text

    create_response = await client.post(
        "/api/v1/analytics/levels",
        headers=auth_headers(admin_token),
        json={"name": "Beginner+", "required_points": 15, "description": "Beginner plus"},
    )
    assert create_response.status_code == 201, create_response.text
    level_id = create_response.json()["id"]

    duplicate_points_response = await client.post(
        "/api/v1/analytics/levels",
        headers=auth_headers(admin_token),
        json={"name": "Duplicate points", "required_points": 15},
    )
    assert duplicate_points_response.status_code == 400, duplicate_points_response.text

    get_response = await client.get(
        f"/api/v1/analytics/levels/{level_id}",
        headers=auth_headers(teacher_token),
    )
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["name"] == "Beginner+"

    update_response = await client.patch(
        f"/api/v1/analytics/levels/{level_id}",
        headers=auth_headers(admin_token),
        json={"name": "Beginner Plus Updated", "required_points": 16},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["name"] == "Beginner Plus Updated"
    assert update_response.json()["required_points"] == 16

    delete_response = await client.delete(
        f"/api/v1/analytics/levels/{level_id}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204, delete_response.text

    not_found_response = await client.get(
        f"/api/v1/analytics/levels/{level_id}",
        headers=auth_headers(admin_token),
    )
    assert not_found_response.status_code == 404, not_found_response.text


async def test_level_admin_crud_invalidates_level_related_caches(client, db, monkeypatch):
    captured_calls: list[tuple[str, ...]] = []

    async def _fake_bump_cache_namespace(*namespaces: str):
        captured_calls.append(tuple(namespaces))

    monkeypatch.setattr("app.services.level_admin_service.bump_cache_namespace", _fake_bump_cache_namespace)

    admin = await seed_user(
        db,
        username="level_admin_cache@example.com",
        password="admin123",
        role="admin",
        full_name="Level Admin Cache",
    )
    admin_token = await login(client, admin.username, "admin123")

    create_response = await client.post(
        "/api/v1/analytics/levels",
        headers=auth_headers(admin_token),
        json={"name": "Cache Level", "required_points": 123},
    )
    assert create_response.status_code == 201, create_response.text
    level_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/analytics/levels/{level_id}",
        headers=auth_headers(admin_token),
        json={"required_points": 124},
    )
    assert update_response.status_code == 200, update_response.text

    delete_response = await client.delete(
        f"/api/v1/analytics/levels/{level_id}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204, delete_response.text

    assert len(captured_calls) == 3
    for call in captured_calls:
        assert set(call) == {"levels", "tests", "materials"}


async def test_achievement_definition_admin_full_crud(client, db):
    admin = await seed_user(
        db,
        username="achievement_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Achievement Admin",
    )
    user = await seed_user(
        db,
        username="achievement_user@example.com",
        password="user123",
        role="user",
        full_name="Achievement User",
    )

    admin_token = await login(client, admin.username, "admin123")
    user_token = await login(client, user.username, "user123")

    forbidden_list_response = await client.get(
        "/api/v1/analytics/achievement-definitions",
        headers=auth_headers(user_token),
    )
    assert forbidden_list_response.status_code == 403, forbidden_list_response.text

    create_response = await client.post(
        "/api/v1/analytics/achievement-definitions",
        headers=auth_headers(admin_token),
        json={
            "code": "achievement_crud_custom",
            "title": "Achievement CRUD",
            "description": "Created in integration test",
            "reward": "Badge",
            "criteria_type": "completed_attempts",
            "threshold_value": 2,
            "is_active": True,
        },
    )
    assert create_response.status_code == 201, create_response.text
    achievement_definition_id = create_response.json()["id"]

    invalid_threshold_response = await client.post(
        "/api/v1/analytics/achievement-definitions",
        headers=auth_headers(admin_token),
        json={
            "code": "achievement_invalid_threshold",
            "title": "Invalid",
            "description": "Invalid",
            "criteria_type": "streak_days",
            "threshold_value": 0,
            "is_active": True,
        },
    )
    assert invalid_threshold_response.status_code == 400, invalid_threshold_response.text

    update_response = await client.patch(
        f"/api/v1/analytics/achievement-definitions/{achievement_definition_id}",
        headers=auth_headers(admin_token),
        json={
            "title": "Achievement CRUD Updated",
            "criteria_type": "streak_days",
            "threshold_value": 3,
            "is_active": False,
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["title"] == "Achievement CRUD Updated"
    assert update_response.json()["criteria_type"] == "streak_days"
    assert update_response.json()["threshold_value"] == 3
    assert update_response.json()["is_active"] is False

    delete_response = await client.delete(
        f"/api/v1/analytics/achievement-definitions/{achievement_definition_id}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204, delete_response.text

    not_found_response = await client.get(
        f"/api/v1/analytics/achievement-definitions/{achievement_definition_id}",
        headers=auth_headers(admin_token),
    )
    assert not_found_response.status_code == 404, not_found_response.text

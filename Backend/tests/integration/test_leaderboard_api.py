from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.points_ledger import PointsLedger
from app.models.user import User
from app.repositories import analytics_repo, group_repo

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


async def test_leaderboard_scope_and_period(client, db):
    admin = await seed_user(
        db,
        username="leaderboard_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Leaderboard Admin",
    )
    teacher = await seed_user(
        db,
        username="leaderboard_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Leaderboard Teacher",
    )
    student_group = await seed_user(
        db,
        username="leaderboard_group_student@example.com",
        password="stud123",
        role="user",
        full_name="Leaderboard Group Student",
    )
    student_global = await seed_user(
        db,
        username="leaderboard_global_student@example.com",
        password="stud123",
        role="user",
        full_name="Leaderboard Global Student",
    )

    group = await group_repo.create_group(db, "leaderboard-group", teacher.id)
    await group_repo.add_user_to_group(db, group, student_group.id)

    await analytics_repo.apply_points_transaction(
        db,
        user_id=student_group.id,
        points_delta=50.0,
        reason_code="seed_points_group",
        source_type="seed",
        idempotency_key="seed_points_group",
    )
    await analytics_repo.apply_points_transaction(
        db,
        user_id=student_global.id,
        points_delta=200.0,
        reason_code="seed_points_global",
        source_type="seed",
        idempotency_key="seed_points_global",
    )

    global_ledger = (
        await db.execute(
            select(PointsLedger).where(
                PointsLedger.user_id == student_global.id,
                PointsLedger.idempotency_key == "seed_points_global",
            )
        )
    ).scalars().first()
    assert global_ledger is not None
    global_ledger.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=90)
    await db.flush()

    admin_token = await login(client, admin.username, "admin123")
    teacher_token = await login(client, teacher.username, "teach123")
    group_student_token = await login(client, student_group.username, "stud123")

    season_create = await client.post(
        "/api/v1/analytics/seasons",
        headers=auth_headers(admin_token),
        json={
            "code": "leaderboard_spring",
            "title": "Leaderboard Spring",
            "starts_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "ends_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "is_active": True,
        },
    )
    assert season_create.status_code == 201, season_create.text
    season_id = season_create.json()["id"]

    leaderboard_all_time = await client.get(
        "/api/v1/analytics/leaderboard?scope=global&period=all_time&limit=200&offset=0",
        headers=auth_headers(group_student_token),
    )
    assert leaderboard_all_time.status_code == 200, leaderboard_all_time.text
    all_time_items = leaderboard_all_time.json()
    assert all_time_items
    all_time_by_user_id = {item["user_id"]: item for item in all_time_items}
    assert student_group.id in all_time_by_user_id
    assert student_global.id in all_time_by_user_id
    assert float(all_time_by_user_id[student_global.id]["total_points"]) > float(
        all_time_by_user_id[student_group.id]["total_points"]
    )

    leaderboard_season = await client.get(
        f"/api/v1/analytics/leaderboard?scope=global&period=season&season_id={season_id}&limit=200&offset=0",
        headers=auth_headers(group_student_token),
    )
    assert leaderboard_season.status_code == 200, leaderboard_season.text
    season_items = leaderboard_season.json()
    assert season_items
    season_by_user_id = {item["user_id"]: item for item in season_items}
    assert student_group.id in season_by_user_id
    assert student_global.id in season_by_user_id
    assert float(season_by_user_id[student_group.id]["total_points"]) > float(
        season_by_user_id[student_global.id]["total_points"]
    )

    teacher_group_leaderboard = await client.get(
        f"/api/v1/analytics/leaderboard?scope=group&period=all_time&group_id={group.id}&limit=10&offset=0",
        headers=auth_headers(teacher_token),
    )
    assert teacher_group_leaderboard.status_code == 200, teacher_group_leaderboard.text
    group_items = teacher_group_leaderboard.json()
    assert len(group_items) == 1
    assert group_items[0]["user_id"] == student_group.id

    forbidden_group_leaderboard = await client.get(
        f"/api/v1/analytics/leaderboard?scope=group&period=all_time&group_id={group.id}&limit=10&offset=0",
        headers=auth_headers(group_student_token),
    )
    assert forbidden_group_leaderboard.status_code == 403, forbidden_group_leaderboard.text

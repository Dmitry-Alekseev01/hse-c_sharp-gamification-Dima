from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import get_password_hash
from app.models.test_attempt import TestAttempt as AttemptModel
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


async def seed_user(db, *, username: str, password: str, role: str) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
    )
    db.add(user)
    await db.flush()
    return user


async def test_attempt_state_reports_timer_and_auto_finalizes_expired_attempt(client, db):
    teacher = await seed_user(db, username="timer_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="timer_student@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    create_test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Timer state test",
            "published": True,
            "time_limit_minutes": 1,
            "max_attempts": 2,
        },
    )
    assert create_test_response.status_code == 201, create_test_response.text
    test_id = create_test_response.json()["id"]

    start_attempt_response = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_attempt_response.status_code == 201, start_attempt_response.text
    attempt_id = start_attempt_response.json()["id"]

    initial_state_response = await client.get(
        f"/api/v1/tests/attempts/{attempt_id}/state",
        headers=auth_headers(student_token),
    )
    assert initial_state_response.status_code == 200, initial_state_response.text
    initial_state = initial_state_response.json()
    assert initial_state["attempt_id"] == attempt_id
    assert initial_state["test_id"] == test_id
    assert initial_state["status"] == "in_progress"
    assert initial_state["time_limit_minutes"] == 1
    assert initial_state["is_expired"] is False
    assert initial_state["expired_reason"] is None
    assert initial_state["remaining_seconds"] is not None
    assert 0 <= initial_state["remaining_seconds"] <= 60

    attempt = await db.get(AttemptModel, attempt_id)
    assert attempt is not None
    attempt.started_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=2)
    await db.flush()

    expired_state_response = await client.get(
        f"/api/v1/tests/attempts/{attempt_id}/state",
        headers=auth_headers(student_token),
    )
    assert expired_state_response.status_code == 200, expired_state_response.text
    expired_state = expired_state_response.json()
    assert expired_state["status"] == "completed"
    assert expired_state["is_expired"] is True
    assert expired_state["expired_reason"] == "time_limit"
    assert expired_state["remaining_seconds"] == 0

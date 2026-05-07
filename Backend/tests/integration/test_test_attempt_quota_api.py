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


async def test_attempt_quota_endpoint_and_retry_limit(client, db):
    teacher = await seed_user(db, username="quota_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="quota_student@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    create_test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Attempts quota test",
            "published": True,
            "max_attempts": 2,
        },
    )
    assert create_test_response.status_code == 201, create_test_response.text
    test_id = create_test_response.json()["id"]

    quota_initial = await client.get(
        f"/api/v1/tests/{test_id}/attempts/quota",
        headers=auth_headers(student_token),
    )
    assert quota_initial.status_code == 200, quota_initial.text
    assert quota_initial.json()["test_id"] == test_id
    assert quota_initial.json()["max_attempts"] == 2
    assert quota_initial.json()["completed_attempts"] == 0
    assert quota_initial.json()["remaining_attempts"] == 2
    assert quota_initial.json()["has_active_attempt"] is False
    assert quota_initial.json()["attempt_state"] == "can_start"
    assert quota_initial.json()["can_start"] is True
    assert quota_initial.json()["can_resume"] is False

    start_first = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_first.status_code == 201, start_first.text
    first_attempt_id = start_first.json()["id"]
    assert start_first.json()["action"] == "started"

    start_first_again = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_first_again.status_code == 201, start_first_again.text
    assert start_first_again.json()["id"] == first_attempt_id
    assert start_first_again.json()["action"] == "resumed"

    quota_with_active = await client.get(
        f"/api/v1/tests/{test_id}/attempts/quota",
        headers=auth_headers(student_token),
    )
    assert quota_with_active.status_code == 200, quota_with_active.text
    assert quota_with_active.json()["has_active_attempt"] is True
    assert quota_with_active.json()["remaining_attempts"] == 2
    assert quota_with_active.json()["attempt_state"] == "can_resume"
    assert quota_with_active.json()["can_resume"] is True

    complete_first = await client.post(
        f"/api/v1/tests/attempts/{first_attempt_id}/complete",
        headers=auth_headers(student_token),
    )
    assert complete_first.status_code == 200, complete_first.text

    quota_after_first = await client.get(
        f"/api/v1/tests/{test_id}/attempts/quota",
        headers=auth_headers(student_token),
    )
    assert quota_after_first.status_code == 200, quota_after_first.text
    assert quota_after_first.json()["completed_attempts"] == 1
    assert quota_after_first.json()["remaining_attempts"] == 1
    assert quota_after_first.json()["has_active_attempt"] is False
    assert quota_after_first.json()["attempt_state"] == "can_start"

    start_second = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_second.status_code == 201, start_second.text
    second_attempt_id = start_second.json()["id"]
    assert second_attempt_id != first_attempt_id
    assert start_second.json()["action"] == "started"

    complete_second = await client.post(
        f"/api/v1/tests/attempts/{second_attempt_id}/complete",
        headers=auth_headers(student_token),
    )
    assert complete_second.status_code == 200, complete_second.text

    quota_after_second = await client.get(
        f"/api/v1/tests/{test_id}/attempts/quota",
        headers=auth_headers(student_token),
    )
    assert quota_after_second.status_code == 200, quota_after_second.text
    assert quota_after_second.json()["completed_attempts"] == 2
    assert quota_after_second.json()["remaining_attempts"] == 0
    assert quota_after_second.json()["attempt_state"] == "blocked"
    assert quota_after_second.json()["block_reason"] == "no_attempts"

    start_third = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_third.status_code == 409, start_third.text
    assert "No attempts remaining" in start_third.json()["detail"]
    assert start_third.json()["block_reason"] == "no_attempts"


async def test_start_attempt_returns_409_for_expired_active_then_allows_retry_on_next_call(client, db):
    teacher = await seed_user(db, username="quota_teacher_expired@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="quota_student_expired@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    create_test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Attempts expired active flow",
            "published": True,
            "max_attempts": 2,
            "time_limit_minutes": 1,
        },
    )
    assert create_test_response.status_code == 201, create_test_response.text
    test_id = create_test_response.json()["id"]

    start_first = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_first.status_code == 201, start_first.text
    first_attempt_id = start_first.json()["id"]

    attempt = await db.get(AttemptModel, first_attempt_id)
    assert attempt is not None
    attempt.started_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=2)
    await db.flush()

    start_after_expire = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_after_expire.status_code == 409, start_after_expire.text
    assert "time limit" in start_after_expire.json()["detail"].lower()
    assert start_after_expire.json()["block_reason"] == "time_limit_exceeded"

    quota_after_expire = await client.get(
        f"/api/v1/tests/{test_id}/attempts/quota",
        headers=auth_headers(student_token),
    )
    assert quota_after_expire.status_code == 200, quota_after_expire.text
    assert quota_after_expire.json()["completed_attempts"] == 1
    assert quota_after_expire.json()["remaining_attempts"] == 1
    assert quota_after_expire.json()["has_active_attempt"] is False
    assert quota_after_expire.json()["attempt_state"] == "can_start"

    start_second = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_second.status_code == 201, start_second.text
    assert start_second.json()["id"] != first_attempt_id
    assert start_second.json()["action"] == "started"


async def test_attempts_resume_after_teacher_increases_max_attempts(client, db):
    teacher = await seed_user(db, username="quota_teacher_increase@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="quota_student_increase@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    create_test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Attempts increase from admin flow",
            "published": True,
            "max_attempts": 1,
        },
    )
    assert create_test_response.status_code == 201, create_test_response.text
    test_id = create_test_response.json()["id"]

    start_first = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_first.status_code == 201, start_first.text
    first_attempt_id = start_first.json()["id"]

    complete_first = await client.post(
        f"/api/v1/tests/attempts/{first_attempt_id}/complete",
        headers=auth_headers(student_token),
    )
    assert complete_first.status_code == 200, complete_first.text

    blocked_start = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert blocked_start.status_code == 409, blocked_start.text
    assert "No attempts remaining" in blocked_start.json()["detail"]
    assert blocked_start.json()["block_reason"] == "no_attempts"

    increase_attempts_response = await client.patch(
        f"/api/v1/tests/{test_id}",
        headers=auth_headers(teacher_token),
        json={"max_attempts": 99},
    )
    assert increase_attempts_response.status_code == 200, increase_attempts_response.text
    assert increase_attempts_response.json()["max_attempts"] == 99

    quota_after_increase = await client.get(
        f"/api/v1/tests/{test_id}/attempts/quota",
        headers=auth_headers(student_token),
    )
    assert quota_after_increase.status_code == 200, quota_after_increase.text
    assert quota_after_increase.json()["max_attempts"] == 99
    assert quota_after_increase.json()["completed_attempts"] == 1
    assert quota_after_increase.json()["remaining_attempts"] == 98
    assert quota_after_increase.json()["attempt_state"] == "can_start"

    resumed_start = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert resumed_start.status_code == 201, resumed_start.text
    assert resumed_start.json()["id"] != first_attempt_id
    assert resumed_start.json()["action"] == "started"


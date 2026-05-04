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
    assert quota_initial.json() == {
        "test_id": test_id,
        "max_attempts": 2,
        "completed_attempts": 0,
        "remaining_attempts": 2,
        "has_active_attempt": False,
    }

    start_first = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_first.status_code == 201, start_first.text
    first_attempt_id = start_first.json()["id"]

    start_first_again = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_first_again.status_code == 201, start_first_again.text
    assert start_first_again.json()["id"] == first_attempt_id

    quota_with_active = await client.get(
        f"/api/v1/tests/{test_id}/attempts/quota",
        headers=auth_headers(student_token),
    )
    assert quota_with_active.status_code == 200, quota_with_active.text
    assert quota_with_active.json()["has_active_attempt"] is True
    assert quota_with_active.json()["remaining_attempts"] == 2

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

    start_second = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_second.status_code == 201, start_second.text
    second_attempt_id = start_second.json()["id"]
    assert second_attempt_id != first_attempt_id

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

    start_third = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_third.status_code == 409, start_third.text
    assert "No attempts remaining" in start_third.json()["detail"]


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

    quota_after_expire = await client.get(
        f"/api/v1/tests/{test_id}/attempts/quota",
        headers=auth_headers(student_token),
    )
    assert quota_after_expire.status_code == 200, quota_after_expire.text
    assert quota_after_expire.json()["completed_attempts"] == 1
    assert quota_after_expire.json()["remaining_attempts"] == 1
    assert quota_after_expire.json()["has_active_attempt"] is False

    start_second = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_second.status_code == 201, start_second.text
    assert start_second.json()["id"] != first_attempt_id

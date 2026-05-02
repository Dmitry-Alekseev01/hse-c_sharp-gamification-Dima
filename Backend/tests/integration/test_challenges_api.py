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


async def test_challenge_progress_and_claim_flow(client, db):
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
    student = await seed_user(
        db,
        username="challenge_student@example.com",
        password="stud123",
        role="user",
        full_name="Challenge Student",
    )

    admin_token = await login(client, admin.username, "admin123")
    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    challenge_create_response = await client.post(
        "/api/v1/analytics/challenges",
        headers=auth_headers(admin_token),
        json={
            "code": "daily_answer_case",
            "title": "Daily Answer x1",
            "description": "Submit at least one answer today",
            "period_type": "daily",
            "event_type": "answer_submitted",
            "target_value": 1,
            "reward_points": 15.0,
            "is_active": True,
        },
    )
    assert challenge_create_response.status_code == 201, challenge_create_response.text
    challenge_id = challenge_create_response.json()["id"]

    forbidden_create_response = await client.post(
        "/api/v1/analytics/challenges",
        headers=auth_headers(teacher_token),
        json={
            "code": "forbidden_create_case",
            "title": "Forbidden",
            "period_type": "daily",
            "event_type": "answer_submitted",
            "target_value": 1,
        },
    )
    assert forbidden_create_response.status_code == 403, forbidden_create_response.text

    test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Challenge flow test",
            "description": "challenge progress trigger",
            "published": True,
        },
    )
    assert test_response.status_code == 201, test_response.text
    test_id = test_response.json()["id"]

    question_response = await client.post(
        "/api/v1/questions/",
        headers=auth_headers(teacher_token),
        json={
            "test_id": test_id,
            "text": "1 + 1 = ?",
            "points": 2.0,
            "is_open_answer": False,
            "choices": [
                {"value": "2", "ordinal": 1, "is_correct": True},
                {"value": "3", "ordinal": 2, "is_correct": False},
            ],
        },
    )
    assert question_response.status_code == 201, question_response.text
    question_payload = question_response.json()
    question_id = question_payload["id"]
    correct_choice_id = next(choice["id"] for choice in question_payload["choices"] if choice["is_correct"])

    attempt_response = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert attempt_response.status_code == 201, attempt_response.text
    attempt_id = attempt_response.json()["id"]

    submit_response = await client.post(
        "/api/v1/answers/",
        headers=auth_headers(student_token),
        json={
            "test_id": test_id,
            "attempt_id": attempt_id,
            "question_id": question_id,
            "answer_payload": str(correct_choice_id),
        },
    )
    assert submit_response.status_code == 201, submit_response.text

    active_challenges_response = await client.get(
        "/api/v1/analytics/me/challenges/active",
        headers=auth_headers(student_token),
    )
    assert active_challenges_response.status_code == 200, active_challenges_response.text
    active_challenges = active_challenges_response.json()
    challenge_progress = next(item for item in active_challenges if item["challenge_id"] == challenge_id)
    assert challenge_progress["is_completed"] is True
    assert challenge_progress["is_claimed"] is False
    assert challenge_progress["progress_value"] >= 1

    claim_response = await client.post(
        f"/api/v1/analytics/me/challenges/{challenge_id}/claim",
        headers=auth_headers(student_token),
    )
    assert claim_response.status_code == 200, claim_response.text
    claim_payload = claim_response.json()
    assert claim_payload["challenge_id"] == challenge_id
    assert claim_payload["reward_points"] == pytest.approx(15.0)

    duplicate_claim_response = await client.post(
        f"/api/v1/analytics/me/challenges/{challenge_id}/claim",
        headers=auth_headers(student_token),
    )
    assert duplicate_claim_response.status_code == 409, duplicate_claim_response.text

    ledger_response = await client.get(
        "/api/v1/analytics/me/points-ledger",
        headers=auth_headers(student_token),
    )
    assert ledger_response.status_code == 200, ledger_response.text
    ledger_items = ledger_response.json()["items"]
    assert any(item["reason_code"] == "challenge_claim" for item in ledger_items)

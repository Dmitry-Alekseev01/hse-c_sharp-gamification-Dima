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


async def seed_user(db, *, username: str, password: str, role: str) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_test(client, token: str, *, title: str) -> dict:
    response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(token),
        json={"title": title, "published": True, "max_attempts": 2},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_open_question(client, token: str, *, test_id: int, text: str) -> dict:
    response = await client.post(
        "/api/v1/questions/",
        headers=auth_headers(token),
        json={
            "test_id": test_id,
            "text": text,
            "points": 3.0,
            "is_open_answer": True,
            "choices": [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_mcq_question(client, token: str, *, test_id: int, text: str) -> dict:
    response = await client.post(
        "/api/v1/questions/",
        headers=auth_headers(token),
        json={
            "test_id": test_id,
            "text": text,
            "points": 2.0,
            "is_open_answer": False,
            "choices": [
                {"value": "Correct", "ordinal": 1, "is_correct": True},
                {"value": "Wrong", "ordinal": 2, "is_correct": False},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _start_attempt(client, token: str, test_id: int) -> dict:
    response = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_answers_api_accepts_blank_open_payload_as_skipped(client, db):
    teacher = await seed_user(db, username="answers_blank_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="answers_blank_student@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    created_test = await _create_test(client, teacher_token, title="Blank open payload")
    question = await _create_open_question(
        client,
        teacher_token,
        test_id=created_test["id"],
        text="Explain interfaces",
    )
    attempt = await _start_attempt(client, student_token, created_test["id"])

    response = await client.post(
        "/api/v1/answers/",
        headers=auth_headers(student_token),
        json={
            "test_id": created_test["id"],
            "attempt_id": attempt["id"],
            "question_id": question["id"],
            "answer_payload": "   ",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["score"] == 0.0

    pending = await client.get("/api/v1/answers/pending/open", headers=auth_headers(teacher_token))
    assert pending.status_code == 200, pending.text
    pending_ids = {item["id"] for item in pending.json()}
    assert payload["id"] not in pending_ids


async def test_answers_api_accepts_null_closed_payload_as_skipped(client, db):
    teacher = await seed_user(db, username="answers_null_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="answers_null_student@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    created_test = await _create_test(client, teacher_token, title="Null closed payload")
    question = await _create_mcq_question(
        client,
        teacher_token,
        test_id=created_test["id"],
        text="Pick one",
    )
    attempt = await _start_attempt(client, student_token, created_test["id"])

    response = await client.post(
        "/api/v1/answers/",
        headers=auth_headers(student_token),
        json={
            "test_id": created_test["id"],
            "attempt_id": attempt["id"],
            "question_id": question["id"],
            "answer_payload": "null",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["score"] == 0.0

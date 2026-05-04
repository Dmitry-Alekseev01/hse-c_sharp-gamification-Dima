import pytest

from app.api.v1.routers import answers as answers_router
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


async def _create_test(client, token: str, *, title: str, published: bool = True) -> dict:
    response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(token),
        json={
            "title": title,
            "max_score": 10,
            "max_attempts": 2,
            "published": published,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_mcq_question(client, token: str, *, test_id: int, text: str, points: float = 1.0) -> dict:
    response = await client.post(
        "/api/v1/questions/",
        headers=auth_headers(token),
        json={
            "test_id": test_id,
            "text": text,
            "points": points,
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


async def _submit_answer(client, token: str, *, test_id: int, question_id: int, answer_payload: str, attempt_id: int) -> dict:
    response = await client.post(
        "/api/v1/answers/",
        headers=auth_headers(token),
        json={
            "test_id": test_id,
            "question_id": question_id,
            "answer_payload": answer_payload,
            "attempt_id": attempt_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_answers_by_test_is_cached_and_invalidated_after_new_submission(client, db, monkeypatch):
    teacher = await seed_user(db, username="answers_cache_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="answers_cache_student@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    test_payload = await _create_test(client, teacher_token, title="Answers cache test", published=True)
    question_one = await _create_mcq_question(
        client,
        teacher_token,
        test_id=test_payload["id"],
        text="Q1",
        points=2.0,
    )
    question_two = await _create_mcq_question(
        client,
        teacher_token,
        test_id=test_payload["id"],
        text="Q2",
        points=2.0,
    )

    attempt = await _start_attempt(client, student_token, test_payload["id"])
    await _submit_answer(
        client,
        student_token,
        test_id=test_payload["id"],
        question_id=question_one["id"],
        answer_payload=str(question_one["choices"][0]["id"]),
        attempt_id=attempt["id"],
    )

    call_counter = {"count": 0}
    visible_counter = {"count": 0}
    original_get_answers = answers_router.answer_repo.get_answers_for_test
    original_get_visible_test = answers_router.get_visible_test

    async def counted_get_answers(*args, **kwargs):
        call_counter["count"] += 1
        return await original_get_answers(*args, **kwargs)

    async def counted_get_visible_test(*args, **kwargs):
        visible_counter["count"] += 1
        return await original_get_visible_test(*args, **kwargs)

    monkeypatch.setattr(answers_router.answer_repo, "get_answers_for_test", counted_get_answers, raising=True)
    monkeypatch.setattr(answers_router, "get_visible_test", counted_get_visible_test, raising=True)

    first_response = await client.get(f"/api/v1/answers/test/{test_payload['id']}", headers=auth_headers(student_token))
    assert first_response.status_code == 200, first_response.text
    assert len(first_response.json()) == 1
    assert call_counter["count"] == 1

    second_response = await client.get(f"/api/v1/answers/test/{test_payload['id']}", headers=auth_headers(student_token))
    assert second_response.status_code == 200, second_response.text
    assert len(second_response.json()) == 1
    assert call_counter["count"] == 1
    assert visible_counter["count"] == 1

    await _submit_answer(
        client,
        student_token,
        test_id=test_payload["id"],
        question_id=question_two["id"],
        answer_payload=str(question_two["choices"][0]["id"]),
        attempt_id=attempt["id"],
    )
    before_third_get_visible = visible_counter["count"]

    third_response = await client.get(f"/api/v1/answers/test/{test_payload['id']}", headers=auth_headers(student_token))
    assert third_response.status_code == 200, third_response.text
    assert len(third_response.json()) == 2
    assert call_counter["count"] == 2
    assert visible_counter["count"] == before_third_get_visible + 1

    fourth_response = await client.get(f"/api/v1/answers/test/{test_payload['id']}", headers=auth_headers(student_token))
    assert fourth_response.status_code == 200, fourth_response.text
    assert len(fourth_response.json()) == 2
    assert call_counter["count"] == 2

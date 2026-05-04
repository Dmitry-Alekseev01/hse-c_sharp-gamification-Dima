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


async def _create_test(client, token: str, *, title: str, published: bool = True) -> dict:
    response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(token),
        json={
            "title": title,
            "max_score": 5,
            "max_attempts": 2,
            "published": published,
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
            "points": 1.0,
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


async def _fetch_tests_page_bundle(client, token: str) -> dict:
    tests_response = await client.get("/api/v1/tests/", headers=auth_headers(token))
    assert tests_response.status_code == 200, tests_response.text
    tests_payload = tests_response.json()
    test_ids = [item["id"] for item in tests_payload]

    content_question_counts: dict[int, int] = {}
    answers_count: dict[int, int] = {}

    for test_id in test_ids:
        content_response = await client.get(
            f"/api/v1/tests/{test_id}/content",
            headers=auth_headers(token),
        )
        assert content_response.status_code == 200, content_response.text
        content_question_counts[test_id] = len(content_response.json().get("questions", []))

        answers_response = await client.get(
            f"/api/v1/answers/test/{test_id}",
            headers=auth_headers(token),
        )
        assert answers_response.status_code == 200, answers_response.text
        answers_count[test_id] = len(answers_response.json())

    return {
        "test_ids": test_ids,
        "content_question_counts": content_question_counts,
        "answers_count": answers_count,
    }


async def test_tests_profile_tests_navigation_sequence_is_consistent(client, db):
    teacher = await seed_user(db, username="nav_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="nav_student@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    test_one = await _create_test(client, teacher_token, title="Navigation test one", published=True)
    test_two = await _create_test(client, teacher_token, title="Navigation test two", published=True)

    question_one = await _create_mcq_question(client, teacher_token, test_id=test_one["id"], text="Q1")
    await _create_mcq_question(client, teacher_token, test_id=test_two["id"], text="Q2")

    attempt = await _start_attempt(client, student_token, test_one["id"])
    await _submit_answer(
        client,
        student_token,
        test_id=test_one["id"],
        question_id=question_one["id"],
        answer_payload=str(question_one["choices"][0]["id"]),
        attempt_id=attempt["id"],
    )

    first_bundle = await _fetch_tests_page_bundle(client, student_token)

    dashboard_response = await client.get(
        "/api/v1/analytics/me/learning-dashboard",
        headers=auth_headers(student_token),
    )
    assert dashboard_response.status_code == 200, dashboard_response.text
    dashboard_payload = dashboard_response.json()
    assert dashboard_payload["total_tests"] == len(first_bundle["test_ids"])

    second_bundle = await _fetch_tests_page_bundle(client, student_token)

    assert first_bundle["test_ids"] == second_bundle["test_ids"]
    assert first_bundle["content_question_counts"] == second_bundle["content_question_counts"]
    assert first_bundle["answers_count"] == second_bundle["answers_count"]


async def test_tests_and_content_repeat_requests_use_cache(client, db, monkeypatch):
    from app.api.v1.routers import tests as tests_router

    teacher = await seed_user(db, username="cache_nav_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="cache_nav_student@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    test_payload = await _create_test(client, teacher_token, title="Cache navigation test", published=True)
    await _create_mcq_question(client, teacher_token, test_id=test_payload["id"], text="Cache Q")

    counters = {"list_tests": 0, "list_questions_for_test": 0}
    original_list_tests = tests_router.test_repo.list_tests
    original_list_questions_for_test = tests_router.question_repo.list_questions_for_test

    async def counted_list_tests(*args, **kwargs):
        counters["list_tests"] += 1
        return await original_list_tests(*args, **kwargs)

    async def counted_list_questions_for_test(*args, **kwargs):
        counters["list_questions_for_test"] += 1
        return await original_list_questions_for_test(*args, **kwargs)

    monkeypatch.setattr(tests_router.test_repo, "list_tests", counted_list_tests)
    monkeypatch.setattr(tests_router.question_repo, "list_questions_for_test", counted_list_questions_for_test)

    first_tests = await client.get("/api/v1/tests/", headers=auth_headers(student_token))
    assert first_tests.status_code == 200, first_tests.text
    second_tests = await client.get("/api/v1/tests/", headers=auth_headers(student_token))
    assert second_tests.status_code == 200, second_tests.text
    assert counters["list_tests"] == 1

    first_content = await client.get(
        f"/api/v1/tests/{test_payload['id']}/content",
        headers=auth_headers(student_token),
    )
    assert first_content.status_code == 200, first_content.text
    second_content = await client.get(
        f"/api/v1/tests/{test_payload['id']}/content",
        headers=auth_headers(student_token),
    )
    assert second_content.status_code == 200, second_content.text
    assert counters["list_questions_for_test"] == 1

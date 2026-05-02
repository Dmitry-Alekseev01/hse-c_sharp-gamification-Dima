import pytest

from app.core.security import get_password_hash
from app.models.level import Level
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


async def _create_test(
    client,
    token: str,
    *,
    title: str,
    max_score: int,
    max_attempts: int,
    required_level_id: int | None = None,
) -> dict:
    response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(token),
        json={
            "title": title,
            "max_score": max_score,
            "max_attempts": max_attempts,
            "published": True,
            "required_level_id": required_level_id,
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


async def _complete_attempt(client, token: str, attempt_id: int) -> dict:
    response = await client.post(
        f"/api/v1/tests/attempts/{attempt_id}/complete",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _create_material(client, token: str, *, title: str, required_level_id: int | None = None) -> dict:
    response = await client.post(
        "/api/v1/materials/",
        headers=auth_headers(token),
        json={
            "title": title,
            "required_level_id": required_level_id,
            "blocks": [
                {
                    "block_type": "text",
                    "title": f"{title} block",
                    "body": "content",
                    "order_index": 0,
                }
            ],
            "attachments": [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_learning_dashboard_aggregates_home_personal_analytics_data(client, db):
    teacher = await seed_user(db, username="dash_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="dash_student@example.com", password="stud123", role="user")
    locked_level = Level(name="Locked level", required_points=500)
    db.add(locked_level)
    await db.flush()

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    completed_test = await _create_test(
        client,
        teacher_token,
        title="Dashboard completed test",
        max_score=5,
        max_attempts=2,
    )
    completed_question = await _create_mcq_question(
        client,
        teacher_token,
        test_id=completed_test["id"],
        text="Completed question",
        points=5.0,
    )

    in_progress_test = await _create_test(
        client,
        teacher_token,
        title="Dashboard in-progress test",
        max_score=4,
        max_attempts=2,
    )
    in_progress_question = await _create_mcq_question(
        client,
        teacher_token,
        test_id=in_progress_test["id"],
        text="In-progress question",
        points=4.0,
    )

    locked_test = await _create_test(
        client,
        teacher_token,
        title="Dashboard locked test",
        max_score=3,
        max_attempts=1,
        required_level_id=locked_level.id,
    )
    assert locked_test["required_level_id"] == locked_level.id

    await _create_material(client, teacher_token, title="Visible material", required_level_id=None)
    await _create_material(client, teacher_token, title="Locked material", required_level_id=locked_level.id)

    completed_attempt = await _start_attempt(client, student_token, completed_test["id"])
    await _submit_answer(
        client,
        student_token,
        test_id=completed_test["id"],
        question_id=completed_question["id"],
        answer_payload=str(completed_question["choices"][0]["id"]),
        attempt_id=completed_attempt["id"],
    )
    await _complete_attempt(client, student_token, completed_attempt["id"])

    active_attempt = await _start_attempt(client, student_token, in_progress_test["id"])
    await _submit_answer(
        client,
        student_token,
        test_id=in_progress_test["id"],
        question_id=in_progress_question["id"],
        answer_payload=str(in_progress_question["choices"][1]["id"]),
        attempt_id=active_attempt["id"],
    )

    student_response = await client.get("/api/v1/analytics/me/learning-dashboard", headers=auth_headers(student_token))
    assert student_response.status_code == 200, student_response.text
    payload = student_response.json()

    assert payload["user_id"] == student.id
    assert payload["total_materials"] == 1
    assert payload["total_tests"] == 2
    assert payload["completed_tests"] == 1
    assert payload["tests_with_score"] == 1
    assert payload["average_score_percent"] == pytest.approx(100.0)

    by_test_id = {item["test_id"]: item for item in payload["test_results"]}
    assert completed_test["id"] in by_test_id
    assert in_progress_test["id"] in by_test_id
    assert locked_test["id"] not in by_test_id

    assert by_test_id[completed_test["id"]]["user_status"] == "completed"
    assert by_test_id[completed_test["id"]]["score_percent"] == pytest.approx(100.0)
    assert by_test_id[completed_test["id"]]["completed_attempts"] == 1

    assert by_test_id[in_progress_test["id"]]["user_status"] == "in_progress"
    assert by_test_id[in_progress_test["id"]]["has_active_attempt"] is True
    assert by_test_id[in_progress_test["id"]]["score_percent"] is None

    teacher_response = await client.get("/api/v1/analytics/me/learning-dashboard", headers=auth_headers(teacher_token))
    assert teacher_response.status_code == 200, teacher_response.text
    teacher_payload = teacher_response.json()
    teacher_test_ids = {item["test_id"] for item in teacher_payload["test_results"]}
    assert completed_test["id"] in teacher_test_ids
    assert in_progress_test["id"] in teacher_test_ids
    assert locked_test["id"] in teacher_test_ids
    assert teacher_payload["total_materials"] == 2

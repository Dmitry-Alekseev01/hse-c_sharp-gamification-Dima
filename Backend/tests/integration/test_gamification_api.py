import pytest

from app.core.security import get_password_hash
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


async def test_achievements_and_points_ledger_end_to_end(client, db):
    teacher = await seed_user(
        db,
        username="gamification_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Gamification Teacher",
    )
    student = await seed_user(
        db,
        username="gamification_student@example.com",
        password="stud123",
        role="user",
        full_name="Gamification Student",
    )

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Gamification MCQ",
            "description": "points + achievements flow",
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
            "text": "2 + 3 = ?",
            "points": 5.0,
            "is_open_answer": False,
            "choices": [
                {"value": "4", "ordinal": 1, "is_correct": False},
                {"value": "5", "ordinal": 2, "is_correct": True},
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

    answer_response = await client.post(
        "/api/v1/answers/",
        headers=auth_headers(student_token),
        json={
            "test_id": test_id,
            "attempt_id": attempt_id,
            "question_id": question_id,
            "answer_payload": str(correct_choice_id),
        },
    )
    assert answer_response.status_code == 201, answer_response.text
    assert answer_response.json()["score"] == pytest.approx(5.0)

    complete_response = await client.post(
        f"/api/v1/tests/attempts/{attempt_id}/complete",
        headers=auth_headers(student_token),
    )
    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["status"] == "completed"

    achievements_response = await client.get(
        "/api/v1/analytics/me/achievements",
        headers=auth_headers(student_token),
    )
    assert achievements_response.status_code == 200, achievements_response.text
    achievements = achievements_response.json()
    first_steps = next(item for item in achievements if item["code"] == "first_steps")
    assert first_steps["earned"] is True
    assert first_steps["earned_at"] is not None

    ledger_response = await client.get(
        "/api/v1/analytics/me/points-ledger",
        headers=auth_headers(student_token),
    )
    assert ledger_response.status_code == 200, ledger_response.text
    ledger_payload = ledger_response.json()
    assert ledger_payload["items"], "points ledger should contain at least one event"
    assert any(item["reason_code"] == "answer_auto_graded" for item in ledger_payload["items"])


async def test_teacher_admin_student_achievements_and_ledger_access(client, db):
    teacher = await seed_user(
        db,
        username="access_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Access Teacher",
    )
    admin = await seed_user(
        db,
        username="access_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Access Admin",
    )
    student = await seed_user(
        db,
        username="access_student@example.com",
        password="stud123",
        role="user",
        full_name="Access Student",
    )
    outsider_teacher = await seed_user(
        db,
        username="access_outsider@example.com",
        password="teach123",
        role="teacher",
        full_name="Access Outsider",
    )

    group = await group_repo.create_group(db, "access-group", teacher.id)
    await group_repo.add_user_to_group(db, group, student.id)

    await analytics_repo.apply_points_transaction(
        db,
        user_id=student.id,
        points_delta=130.0,
        mark_active=True,
        reason_code="seed_points_access_case",
        source_type="test_seed",
    )

    teacher_token = await login(client, teacher.username, "teach123")
    admin_token = await login(client, admin.username, "admin123")
    student_token = await login(client, student.username, "stud123")
    outsider_token = await login(client, outsider_teacher.username, "teach123")

    teacher_achievements_response = await client.get(
        f"/api/v1/analytics/user/{student.id}/achievements",
        headers=auth_headers(teacher_token),
    )
    assert teacher_achievements_response.status_code == 200, teacher_achievements_response.text
    teacher_achievements = teacher_achievements_response.json()
    century_points = next(item for item in teacher_achievements if item["code"] == "century_points")
    assert century_points["earned"] is True
    assert century_points["earned_at"] is not None

    teacher_ledger_response = await client.get(
        f"/api/v1/analytics/user/{student.id}/points-ledger",
        headers=auth_headers(teacher_token),
    )
    assert teacher_ledger_response.status_code == 200, teacher_ledger_response.text
    teacher_ledger = teacher_ledger_response.json()
    assert any(item["reason_code"] == "seed_points_access_case" for item in teacher_ledger["items"])

    admin_achievements_response = await client.get(
        f"/api/v1/analytics/user/{student.id}/achievements",
        headers=auth_headers(admin_token),
    )
    assert admin_achievements_response.status_code == 200, admin_achievements_response.text

    admin_ledger_response = await client.get(
        f"/api/v1/analytics/user/{student.id}/points-ledger",
        headers=auth_headers(admin_token),
    )
    assert admin_ledger_response.status_code == 200, admin_ledger_response.text

    student_forbidden_response = await client.get(
        f"/api/v1/analytics/user/{student.id}/achievements",
        headers=auth_headers(student_token),
    )
    assert student_forbidden_response.status_code == 403, student_forbidden_response.text

    outsider_forbidden_response = await client.get(
        f"/api/v1/analytics/user/{student.id}/achievements",
        headers=auth_headers(outsider_token),
    )
    assert outsider_forbidden_response.status_code == 403, outsider_forbidden_response.text

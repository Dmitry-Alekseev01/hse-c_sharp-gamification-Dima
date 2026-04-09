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
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


async def create_seed_user(db, *, username: str, password: str, role: str, full_name: str) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
        full_name=full_name,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_e2e_auth_register_login_and_me(client):
    username = "e2e_user@example.com"
    password = "123456"
    full_name = "E2E User"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": password,
            "full_name": full_name,
        },
    )
    assert register_response.status_code == 201, register_response.text
    created = register_response.json()

    token = await login(client, username, password)

    me_response = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me_response.status_code == 200, me_response.text
    me_payload = me_response.json()
    assert me_payload["username"] == username
    assert me_payload["full_name"] == full_name
    assert me_payload["role"] == "user"

    self_response = await client.get(f"/api/v1/users/{created['id']}", headers=auth_headers(token))
    assert self_response.status_code == 200, self_response.text
    assert self_response.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_e2e_teacher_creates_test_student_solves_mcq(client, db):
    teacher = await create_seed_user(
        db,
        username="teacher_e2e@example.com",
        password="teach123",
        role="teacher",
        full_name="Teacher E2E",
    )
    student = await create_seed_user(
        db,
        username="student_e2e@example.com",
        password="stud123",
        role="user",
        full_name="Student E2E",
    )

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    material_response = await client.post(
        "/api/v1/materials/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Lesson 1",
            "material_type": "lesson",
            "status": "published",
            "description": "Intro",
            "blocks": [
                {
                    "block_type": "text",
                    "title": "Basics",
                    "body": "C# basics",
                    "order_index": 0,
                }
            ],
            "attachments": [],
        },
    )
    assert material_response.status_code == 201, material_response.text

    test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "MCQ Quiz",
            "description": "Simple quiz",
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
            "text": "2 + 2 = ?",
            "points": 5.0,
            "is_open_answer": False,
            "choices": [
                {"value": "3", "ordinal": 1, "is_correct": False},
                {"value": "4", "ordinal": 2, "is_correct": True},
            ],
        },
    )
    assert question_response.status_code == 201, question_response.text
    question_payload = question_response.json()
    question_id = question_payload["id"]
    correct_choice_id = next(choice["id"] for choice in question_payload["choices"] if choice["is_correct"])

    list_tests_response = await client.get(
        "/api/v1/tests/",
        params={"published_only": "true", "limit": 100},
        headers=auth_headers(student_token),
    )
    assert list_tests_response.status_code == 200, list_tests_response.text
    listed_ids = {item["id"] for item in list_tests_response.json()}
    assert test_id in listed_ids

    start_attempt_response = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_attempt_response.status_code == 201, start_attempt_response.text
    attempt_id = start_attempt_response.json()["id"]

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
    assert submit_response.json()["score"] == pytest.approx(5.0)

    complete_response = await client.post(
        f"/api/v1/tests/attempts/{attempt_id}/complete",
        headers=auth_headers(student_token),
    )
    assert complete_response.status_code == 200, complete_response.text
    completed_attempt = complete_response.json()
    assert completed_attempt["status"] == "completed"
    assert completed_attempt["score"] == pytest.approx(5.0)

    my_attempts_response = await client.get(
        f"/api/v1/tests/{test_id}/attempts/me",
        headers=auth_headers(student_token),
    )
    assert my_attempts_response.status_code == 200, my_attempts_response.text
    attempts = my_attempts_response.json()
    assert len(attempts) == 1
    assert attempts[0]["id"] == attempt_id
    assert attempts[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_e2e_open_answer_pending_and_teacher_grading(client, db):
    teacher = await create_seed_user(
        db,
        username="teacher_grade@example.com",
        password="teach123",
        role="teacher",
        full_name="Teacher Grade",
    )
    student = await create_seed_user(
        db,
        username="student_grade@example.com",
        password="stud123",
        role="user",
        full_name="Student Grade",
    )

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Open Quiz",
            "description": "Open question test",
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
            "text": "Explain polymorphism",
            "points": 7.0,
            "is_open_answer": True,
        },
    )
    assert question_response.status_code == 201, question_response.text
    question_id = question_response.json()["id"]

    start_attempt_response = await client.post(
        f"/api/v1/tests/{test_id}/attempts/start",
        headers=auth_headers(student_token),
    )
    assert start_attempt_response.status_code == 201, start_attempt_response.text
    attempt_id = start_attempt_response.json()["id"]

    submit_response = await client.post(
        "/api/v1/answers/",
        headers=auth_headers(student_token),
        json={
            "test_id": test_id,
            "attempt_id": attempt_id,
            "question_id": question_id,
            "answer_payload": "Polymorphism allows one interface, many implementations.",
        },
    )
    assert submit_response.status_code == 201, submit_response.text
    answer_id = submit_response.json()["id"]
    assert submit_response.json()["score"] is None

    pending_response = await client.get(
        "/api/v1/answers/pending/open",
        params={"test_id": test_id},
        headers=auth_headers(teacher_token),
    )
    assert pending_response.status_code == 200, pending_response.text
    pending_items = pending_response.json()
    assert any(item["id"] == answer_id for item in pending_items)
    pending_item = next(item for item in pending_items if item["id"] == answer_id)
    assert pending_item["question_text"] == "Explain polymorphism"
    assert pending_item["student_username"] == student.username

    complete_response = await client.post(
        f"/api/v1/tests/attempts/{attempt_id}/complete",
        headers=auth_headers(student_token),
    )
    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["status"] == "completed"

    grade_response = await client.post(
        f"/api/v1/answers/{answer_id}/grade",
        headers=auth_headers(teacher_token),
        json={"score": 6.0},
    )
    assert grade_response.status_code == 200, grade_response.text
    assert grade_response.json()["score"] == pytest.approx(6.0)

    analytics_response = await client.get(
        f"/api/v1/analytics/user/{student.id}",
        headers=auth_headers(teacher_token),
    )
    assert analytics_response.status_code == 200, analytics_response.text
    analytics_payload = analytics_response.json()
    assert analytics_payload["user_id"] == student.id
    assert analytics_payload["total_points"] == pytest.approx(6.0)


@pytest.mark.asyncio
async def test_e2e_group_management_and_role_access(client, db):
    owner_teacher = await create_seed_user(
        db,
        username="owner_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Owner Teacher",
    )
    other_teacher = await create_seed_user(
        db,
        username="other_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Other Teacher",
    )
    admin = await create_seed_user(
        db,
        username="admin_e2e@example.com",
        password="admin123",
        role="admin",
        full_name="Admin E2E",
    )
    student = await create_seed_user(
        db,
        username="group_student@example.com",
        password="stud123",
        role="user",
        full_name="Group Student",
    )

    owner_token = await login(client, owner_teacher.username, "teach123")
    other_token = await login(client, other_teacher.username, "teach123")
    admin_token = await login(client, admin.username, "admin123")

    create_group_response = await client.post(
        "/api/v1/groups/",
        headers=auth_headers(owner_token),
        json={"name": "BPI-404"},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_payload = create_group_response.json()
    group_id = group_payload["id"]
    assert group_payload["teacher_id"] == owner_teacher.id

    add_member_response = await client.post(
        f"/api/v1/groups/{group_id}/members/{student.id}",
        headers=auth_headers(owner_token),
    )
    assert add_member_response.status_code == 200, add_member_response.text

    group_after_add = await client.get(f"/api/v1/groups/{group_id}", headers=auth_headers(owner_token))
    assert group_after_add.status_code == 200, group_after_add.text
    members = group_after_add.json()["members"]
    assert len(members) == 1
    assert members[0]["user_id"] == student.id
    assert members[0]["username"] == student.username

    owner_groups_response = await client.get("/api/v1/groups/", headers=auth_headers(owner_token))
    assert owner_groups_response.status_code == 200, owner_groups_response.text
    assert any(group["id"] == group_id for group in owner_groups_response.json())

    forbidden_response = await client.get(f"/api/v1/groups/{group_id}", headers=auth_headers(other_token))
    assert forbidden_response.status_code == 403, forbidden_response.text

    admin_group_response = await client.get(f"/api/v1/groups/{group_id}", headers=auth_headers(admin_token))
    assert admin_group_response.status_code == 200, admin_group_response.text
    assert admin_group_response.json()["id"] == group_id

    remove_member_response = await client.delete(
        f"/api/v1/groups/{group_id}/members/{student.id}",
        headers=auth_headers(owner_token),
    )
    assert remove_member_response.status_code == 200, remove_member_response.text

    group_after_remove = await client.get(f"/api/v1/groups/{group_id}", headers=auth_headers(owner_token))
    assert group_after_remove.status_code == 200, group_after_remove.text
    assert group_after_remove.json()["members"] == []

    delete_group_response = await client.delete(f"/api/v1/groups/{group_id}", headers=auth_headers(owner_token))
    assert delete_group_response.status_code == 204, delete_group_response.text

    not_found_response = await client.get(f"/api/v1/groups/{group_id}", headers=auth_headers(admin_token))
    assert not_found_response.status_code == 404, not_found_response.text


@pytest.mark.asyncio
async def test_e2e_test_publish_hide_and_oauth2_token_login(client, db):
    teacher = await create_seed_user(
        db,
        username="teacher_visibility@example.com",
        password="teach123",
        role="teacher",
        full_name="Teacher Visibility",
    )
    student = await create_seed_user(
        db,
        username="student_visibility@example.com",
        password="stud123",
        role="user",
        full_name="Student Visibility",
    )

    teacher_token = await login(client, teacher.username, "teach123")

    create_test_response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(teacher_token),
        json={
            "title": "Visibility Test",
            "description": "publish/hide flow",
            "published": False,
        },
    )
    assert create_test_response.status_code == 201, create_test_response.text
    test_id = create_test_response.json()["id"]
    assert create_test_response.json()["published"] is False

    student_token = await login(client, student.username, "stud123")
    list_before_publish = await client.get(
        "/api/v1/tests/",
        params={"published_only": "true", "limit": 100},
        headers=auth_headers(student_token),
    )
    assert list_before_publish.status_code == 200, list_before_publish.text
    assert test_id not in {item["id"] for item in list_before_publish.json()}

    hidden_detail_response = await client.get(f"/api/v1/tests/{test_id}", headers=auth_headers(student_token))
    assert hidden_detail_response.status_code == 404, hidden_detail_response.text

    publish_response = await client.post(f"/api/v1/tests/{test_id}/publish", headers=auth_headers(teacher_token))
    assert publish_response.status_code == 200, publish_response.text
    assert publish_response.json()["published"] is True

    visible_detail_response = await client.get(f"/api/v1/tests/{test_id}", headers=auth_headers(student_token))
    assert visible_detail_response.status_code == 200, visible_detail_response.text

    hide_response = await client.post(f"/api/v1/tests/{test_id}/hide", headers=auth_headers(teacher_token))
    assert hide_response.status_code == 200, hide_response.text
    assert hide_response.json()["published"] is False

    hidden_again_response = await client.get(f"/api/v1/tests/{test_id}", headers=auth_headers(student_token))
    assert hidden_again_response.status_code == 404, hidden_again_response.text

    token_response = await client.post(
        "/api/v1/auth/token",
        data={"username": student.username, "password": "stud123"},
    )
    assert token_response.status_code == 200, token_response.text
    oauth_token = token_response.json()["access_token"]

    me_response = await client.get("/api/v1/auth/me", headers=auth_headers(oauth_token))
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["username"] == student.username

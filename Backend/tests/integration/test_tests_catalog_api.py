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


async def _create_test(client, token: str, *, title: str, max_score: int, max_attempts: int, published: bool = True) -> dict:
    response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(token),
        json={
            "title": title,
            "max_score": max_score,
            "max_attempts": max_attempts,
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


async def _complete_attempt(client, token: str, attempt_id: int) -> dict:
    response = await client.post(
        f"/api/v1/tests/attempts/{attempt_id}/complete",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_tests_catalog_me_returns_aggregated_states_for_current_user(client, db):
    teacher = await seed_user(db, username="catalog_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="catalog_student@example.com", password="stud123", role="user")

    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    completed_test = await _create_test(
        client,
        teacher_token,
        title="Catalog completed",
        max_score=5,
        max_attempts=3,
        published=True,
    )
    completed_question = await _create_mcq_question(
        client,
        teacher_token,
        test_id=completed_test["id"],
        text="Completed question",
        points=5.0,
    )
    completed_choice_id = completed_question["choices"][0]["id"]

    in_progress_test = await _create_test(
        client,
        teacher_token,
        title="Catalog in progress",
        max_score=4,
        max_attempts=2,
        published=True,
    )
    in_progress_question = await _create_mcq_question(
        client,
        teacher_token,
        test_id=in_progress_test["id"],
        text="In progress question",
        points=4.0,
    )

    not_started_test = await _create_test(
        client,
        teacher_token,
        title="Catalog not started",
        max_score=3,
        max_attempts=1,
        published=True,
    )
    await _create_mcq_question(
        client,
        teacher_token,
        test_id=not_started_test["id"],
        text="Not started question",
        points=3.0,
    )

    hidden_test = await _create_test(
        client,
        teacher_token,
        title="Catalog hidden",
        max_score=7,
        max_attempts=2,
        published=False,
    )
    assert hidden_test["published"] is False

    completed_attempt = await _start_attempt(client, student_token, completed_test["id"])
    await _submit_answer(
        client,
        student_token,
        test_id=completed_test["id"],
        question_id=completed_question["id"],
        answer_payload=str(completed_choice_id),
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

    response = await client.get("/api/v1/tests/catalog/me", headers=auth_headers(student_token))
    assert response.status_code == 200, response.text
    items = response.json()

    ids = {item["id"] for item in items}
    assert completed_test["id"] in ids
    assert in_progress_test["id"] in ids
    assert not_started_test["id"] in ids
    assert hidden_test["id"] not in ids

    completed_item = next(item for item in items if item["id"] == completed_test["id"])
    assert completed_item["total_questions"] == 1
    assert completed_item["user_status"] == "not_started"
    assert completed_item["progress_state"] == "completed"
    assert completed_item["attempt_state"] == "can_start"
    assert completed_item["can_start"] is True
    assert completed_item["can_resume"] is False
    assert completed_item["block_reason"] is None
    assert completed_item["has_active_attempt"] is False
    assert completed_item["active_attempt_id"] is None
    assert completed_item["completed_attempts"] == 1
    assert completed_item["remaining_attempts"] == 2
    assert completed_item["user_score"] == 5.0
    assert completed_item["user_max_score"] == 5.0
    assert completed_item["latest_completed_at"] is not None

    in_progress_item = next(item for item in items if item["id"] == in_progress_test["id"])
    assert in_progress_item["total_questions"] == 1
    assert in_progress_item["user_status"] == "in_progress"
    assert in_progress_item["progress_state"] == "in_progress"
    assert in_progress_item["attempt_state"] == "can_resume"
    assert in_progress_item["can_start"] is False
    assert in_progress_item["can_resume"] is True
    assert in_progress_item["block_reason"] is None
    assert in_progress_item["has_active_attempt"] is True
    assert in_progress_item["active_attempt_id"] == active_attempt["id"]
    assert in_progress_item["completed_attempts"] == 0
    assert in_progress_item["remaining_attempts"] == 2
    assert in_progress_item["user_score"] is None
    assert in_progress_item["user_max_score"] is None

    not_started_item = next(item for item in items if item["id"] == not_started_test["id"])
    assert not_started_item["total_questions"] == 1
    assert not_started_item["user_status"] == "not_started"
    assert not_started_item["progress_state"] == "not_started"
    assert not_started_item["attempt_state"] == "can_start"
    assert not_started_item["can_start"] is True
    assert not_started_item["can_resume"] is False
    assert not_started_item["block_reason"] is None
    assert not_started_item["has_active_attempt"] is False
    assert not_started_item["completed_attempts"] == 0
    assert not_started_item["remaining_attempts"] == 1
    assert not_started_item["user_score"] is None


async def test_tests_catalog_me_forbids_unpublished_scope_for_regular_user(client, db):
    teacher = await seed_user(db, username="catalog_teacher_scope@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="catalog_student_scope@example.com", password="stud123", role="user")
    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    await _create_test(
        client,
        teacher_token,
        title="Catalog scope draft",
        max_score=5,
        max_attempts=1,
        published=False,
    )

    forbidden_response = await client.get(
        "/api/v1/tests/catalog/me?published_only=false",
        headers=auth_headers(student_token),
    )
    assert forbidden_response.status_code == 403, forbidden_response.text


async def test_tests_catalog_me_teacher_can_view_own_unpublished(client, db):
    teacher = await seed_user(db, username="catalog_teacher_unpublished@example.com", password="teach123", role="teacher")
    teacher_token = await login(client, teacher.username, "teach123")

    published = await _create_test(
        client,
        teacher_token,
        title="Teacher visible published",
        max_score=5,
        max_attempts=1,
        published=True,
    )
    draft = await _create_test(
        client,
        teacher_token,
        title="Teacher visible draft",
        max_score=5,
        max_attempts=1,
        published=False,
    )

    response = await client.get(
        "/api/v1/tests/catalog/me?published_only=false",
        headers=auth_headers(teacher_token),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert published["id"] in ids
    assert draft["id"] in ids


async def test_tests_page_alias_returns_same_payload_as_catalog(client, db):
    teacher = await seed_user(db, username="catalog_alias_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="catalog_alias_student@example.com", password="stud123", role="user")
    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    created_test = await _create_test(
        client,
        teacher_token,
        title="Catalog alias test",
        max_score=5,
        max_attempts=2,
        published=True,
    )
    await _create_mcq_question(
        client,
        teacher_token,
        test_id=created_test["id"],
        text="Catalog alias question",
        points=1.0,
    )

    canonical = await client.get("/api/v1/tests/catalog/me", headers=auth_headers(student_token))
    assert canonical.status_code == 200, canonical.text

    alias = await client.get("/api/v1/tests/page/me", headers=auth_headers(student_token))
    assert alias.status_code == 200, alias.text
    assert alias.json() == canonical.json()


async def test_tests_catalog_me_reuses_cache_for_repeat_requests(client, db, monkeypatch):
    from app.api.v1.routers import tests as tests_router

    teacher = await seed_user(db, username="catalog_cache_teacher@example.com", password="teach123", role="teacher")
    student = await seed_user(db, username="catalog_cache_student@example.com", password="stud123", role="user")
    teacher_token = await login(client, teacher.username, "teach123")
    student_token = await login(client, student.username, "stud123")

    created_test = await _create_test(
        client,
        teacher_token,
        title="Catalog cache published",
        max_score=5,
        max_attempts=1,
        published=True,
    )
    await _create_mcq_question(
        client,
        teacher_token,
        test_id=created_test["id"],
        text="Catalog cache question",
        points=1.0,
    )

    counters = {"list_tests": 0, "state_map": 0, "level_context": 0}
    original_list_tests = tests_router.test_repo.list_tests
    original_state_map = tests_router.test_repo.get_user_test_state_map
    original_level_context = tests_router.get_user_level_context

    async def counted_list_tests(*args, **kwargs):
        counters["list_tests"] += 1
        return await original_list_tests(*args, **kwargs)

    async def counted_state_map(*args, **kwargs):
        counters["state_map"] += 1
        return await original_state_map(*args, **kwargs)

    async def counted_level_context(*args, **kwargs):
        counters["level_context"] += 1
        return await original_level_context(*args, **kwargs)

    monkeypatch.setattr(tests_router.test_repo, "list_tests", counted_list_tests, raising=True)
    monkeypatch.setattr(tests_router.test_repo, "get_user_test_state_map", counted_state_map, raising=True)
    monkeypatch.setattr(tests_router, "get_user_level_context", counted_level_context, raising=True)

    first = await client.get("/api/v1/tests/catalog/me", headers=auth_headers(student_token))
    assert first.status_code == 200, first.text
    second = await client.get("/api/v1/tests/catalog/me", headers=auth_headers(student_token))
    assert second.status_code == 200, second.text
    assert second.json() == first.json()

    assert counters["list_tests"] == 1
    assert counters["state_map"] == 1
    assert counters["level_context"] == 1

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


async def create_teacher_test(client, token: str, title: str) -> int:
    response = await client.post(
        "/api/v1/tests/",
        headers=auth_headers(token),
        json={"title": title, "published": False, "max_attempts": 2},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_replace_test_content_allows_owner_and_replaces_questions(client, db):
    owner = await seed_user(
        db,
        username="content_owner_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Content Owner",
    )
    other = await seed_user(
        db,
        username="content_other_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Content Other",
    )

    owner_token = await login(client, owner.username, "teach123")
    other_token = await login(client, other.username, "teach123")
    test_id = await create_teacher_test(client, owner_token, "Content Builder Test")

    forbidden_response = await client.put(
        f"/api/v1/tests/{test_id}/content",
        headers=auth_headers(other_token),
        json={"questions": []},
    )
    assert forbidden_response.status_code == 403, forbidden_response.text

    first_replace_response = await client.put(
        f"/api/v1/tests/{test_id}/content",
        headers=auth_headers(owner_token),
        json={
            "questions": [
                {
                    "text": "2 + 2 = ?",
                    "points": 2.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "3", "ordinal": 1, "is_correct": False},
                        {"value": "4", "ordinal": 2, "is_correct": True},
                    ],
                }
            ]
        },
    )
    assert first_replace_response.status_code == 200, first_replace_response.text
    first_payload = first_replace_response.json()
    assert len(first_payload["questions"]) == 1
    assert first_payload["questions"][0]["text"] == "2 + 2 = ?"

    second_replace_response = await client.put(
        f"/api/v1/tests/{test_id}/content",
        headers=auth_headers(owner_token),
        json={
            "questions": [
                {
                    "text": "Capital of France?",
                    "points": 1.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "Berlin", "ordinal": 1, "is_correct": False},
                        {"value": "Paris", "ordinal": 2, "is_correct": True},
                    ],
                },
                {
                    "text": "Explain polymorphism in C#",
                    "points": 3.0,
                    "is_open_answer": True,
                    "choices": [],
                },
            ]
        },
    )
    assert second_replace_response.status_code == 200, second_replace_response.text
    second_payload = second_replace_response.json()
    assert len(second_payload["questions"]) == 2
    assert second_payload["questions"][0]["text"] == "Capital of France?"
    assert second_payload["questions"][1]["is_open_answer"] is True

    content_response = await client.get(
        f"/api/v1/tests/{test_id}/content",
        headers=auth_headers(owner_token),
    )
    assert content_response.status_code == 200, content_response.text
    content_payload = content_response.json()
    assert len(content_payload["questions"]) == 2


async def test_replace_test_content_validates_closed_question_choices(client, db):
    owner = await seed_user(
        db,
        username="content_validation_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Content Validation",
    )

    owner_token = await login(client, owner.username, "teach123")
    test_id = await create_teacher_test(client, owner_token, "Content Validation Test")

    invalid_response = await client.put(
        f"/api/v1/tests/{test_id}/content",
        headers=auth_headers(owner_token),
        json={
            "questions": [
                {
                    "text": "Which option is correct?",
                    "points": 1.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "A", "ordinal": 1, "is_correct": False},
                        {"value": "B", "ordinal": 2, "is_correct": False},
                    ],
                }
            ]
        },
    )
    assert invalid_response.status_code == 400, invalid_response.text
    assert "at least 1 correct choice" in invalid_response.json()["detail"]

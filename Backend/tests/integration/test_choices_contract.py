import pytest

from app.core.security import get_password_hash
from app.models.question import Question
from app.models.test_ import Test
from app.models.user import User

pytestmark = pytest.mark.asyncio


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client, username: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def seed_teacher(db, *, username: str, password: str) -> User:
    teacher = User(
        username=username,
        password_hash=get_password_hash(password),
        role="teacher",
        full_name="Teacher Contract",
    )
    db.add(teacher)
    await db.flush()
    return teacher


async def test_choices_create_requires_question_id(client, db):
    teacher = await seed_teacher(db, username="choice_contract_teacher@example.com", password="teach123")
    token = await login(client, teacher.username, "teach123")

    response = await client.post(
        "/api/v1/choices/",
        headers=auth_headers(token),
        json={"value": "Option A", "ordinal": 1, "is_correct": False},
    )

    assert response.status_code == 422, response.text


async def test_choices_create_with_question_id_succeeds(client, db):
    teacher = await seed_teacher(db, username="choice_contract_teacher2@example.com", password="teach123")
    token = await login(client, teacher.username, "teach123")

    test = Test(title="Choice contract test", author_id=teacher.id, published=True)
    db.add(test)
    await db.flush()
    question = Question(test_id=test.id, text="Select one", points=1.0, is_open_answer=False)
    db.add(question)
    await db.flush()

    response = await client.post(
        "/api/v1/choices/",
        headers=auth_headers(token),
        json={"question_id": question.id, "value": "Option A", "ordinal": 1, "is_correct": True},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["question_id"] == question.id
    assert body["value"] == "Option A"
    assert body["is_correct"] is True

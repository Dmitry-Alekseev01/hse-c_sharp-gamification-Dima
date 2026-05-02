import pytest

from app.core.security import get_password_hash
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _seed_user(db, *, username: str, password: str, role: str = "user") -> User:
    user = User(username=username, password_hash=get_password_hash(password), role=role)
    db.add(user)
    await db.flush()
    return user


def _assert_admin_cookie_cleared(response) -> None:
    set_cookie = response.headers.get("set-cookie", "")
    assert "admin_session=" in set_cookie
    assert "Max-Age=0" in set_cookie


async def test_json_login_clears_admin_session_cookie(client, db):
    await _seed_user(db, username="session_hygiene_json@example.com", password="user123")

    response = await client.post(
        "/api/v1/auth/login",
        headers={"Cookie": "admin_session=stale_admin_cookie"},
        json={"username": "session_hygiene_json@example.com", "password": "user123"},
    )

    assert response.status_code == 200, response.text
    _assert_admin_cookie_cleared(response)


async def test_oauth_token_login_clears_admin_session_cookie(client, db):
    await _seed_user(db, username="session_hygiene_token@example.com", password="user123")

    response = await client.post(
        "/api/v1/auth/token",
        headers={"Cookie": "admin_session=stale_admin_cookie"},
        data={"username": "session_hygiene_token@example.com", "password": "user123"},
    )

    assert response.status_code == 200, response.text
    _assert_admin_cookie_cleared(response)


async def test_register_clears_admin_session_cookie(client):
    response = await client.post(
        "/api/v1/auth/register",
        headers={"Cookie": "admin_session=stale_admin_cookie"},
        json={
            "username": "session_hygiene_register@example.com",
            "password": "user123",
            "full_name": "Session Hygiene",
        },
    )

    assert response.status_code == 201, response.text
    _assert_admin_cookie_cleared(response)


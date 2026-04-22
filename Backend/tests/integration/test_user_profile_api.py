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


async def seed_user(db, *, username: str, password: str, role: str, full_name: str | None = None) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
        full_name=full_name,
    )
    db.add(user)
    await db.flush()
    return user


async def test_user_can_update_own_profile_and_relogin_after_username_change(client, db):
    user = await seed_user(
        db,
        username="profile_user_old@example.com",
        password="user123",
        role="user",
        full_name="Old Name",
    )
    token = await login(client, user.username, "user123")

    update_name_response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"full_name": "New Name"},
    )
    assert update_name_response.status_code == 200, update_name_response.text
    assert update_name_response.json()["full_name"] == "New Name"

    update_username_response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"username": "profile_user_new@example.com"},
    )
    assert update_username_response.status_code == 200, update_username_response.text
    assert update_username_response.json()["username"] == "profile_user_new@example.com"

    old_token_me = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert old_token_me.status_code == 401, old_token_me.text

    new_token = await login(client, "profile_user_new@example.com", "user123")
    new_me = await client.get("/api/v1/auth/me", headers=auth_headers(new_token))
    assert new_me.status_code == 200, new_me.text
    assert new_me.json()["username"] == "profile_user_new@example.com"
    assert new_me.json()["full_name"] == "New Name"


async def test_profile_update_rejects_duplicate_username(client, db):
    first_user = await seed_user(
        db,
        username="duplicate_first@example.com",
        password="user123",
        role="user",
        full_name="First",
    )
    await seed_user(
        db,
        username="duplicate_second@example.com",
        password="user123",
        role="user",
        full_name="Second",
    )
    token = await login(client, first_user.username, "user123")

    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"username": "duplicate_second@example.com"},
    )
    assert response.status_code == 400, response.text
    assert "username already exists" in response.json()["detail"]


async def test_admin_can_update_user_profile_non_admin_cannot(client, db):
    admin = await seed_user(
        db,
        username="profile_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Admin",
    )
    regular_user = await seed_user(
        db,
        username="profile_target@example.com",
        password="user123",
        role="user",
        full_name="Target",
    )
    non_admin = await seed_user(
        db,
        username="profile_non_admin@example.com",
        password="user123",
        role="user",
        full_name="Non Admin",
    )

    admin_token = await login(client, admin.username, "admin123")
    non_admin_token = await login(client, non_admin.username, "user123")

    admin_update = await client.patch(
        f"/api/v1/users/{regular_user.id}",
        headers=auth_headers(admin_token),
        json={"full_name": "Target Updated"},
    )
    assert admin_update.status_code == 200, admin_update.text
    assert admin_update.json()["full_name"] == "Target Updated"

    non_admin_update = await client.patch(
        f"/api/v1/users/{regular_user.id}",
        headers=auth_headers(non_admin_token),
        json={"full_name": "Should Not Work"},
    )
    assert non_admin_update.status_code == 403, non_admin_update.text

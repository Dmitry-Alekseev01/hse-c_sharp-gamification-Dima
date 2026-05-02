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


async def test_user_can_change_password_and_login_with_new_one(client, db):
    user = await seed_user(
        db,
        username="password_change_api@example.com",
        password="user12345",
        role="user",
        full_name="Password API User",
    )
    token = await login(client, user.username, "user12345")

    change_response = await client.patch(
        "/api/v1/users/me/password",
        headers=auth_headers(token),
        json={
            "current_password": "user12345",
            "new_password": "user67890",
        },
    )
    assert change_response.status_code == 200, change_response.text
    assert change_response.json()["detail"] == "Password updated successfully"

    old_token_me = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert old_token_me.status_code == 401, old_token_me.text

    old_login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "user12345"},
    )
    assert old_login_response.status_code == 401, old_login_response.text

    new_token = await login(client, user.username, "user67890")
    me_response = await client.get("/api/v1/auth/me", headers=auth_headers(new_token))
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["username"] == user.username


async def test_user_change_password_rejects_wrong_current_password(client, db):
    user = await seed_user(
        db,
        username="password_change_api_invalid@example.com",
        password="user12345",
        role="user",
        full_name="Password API Invalid",
    )
    token = await login(client, user.username, "user12345")

    response = await client.patch(
        "/api/v1/users/me/password",
        headers=auth_headers(token),
        json={
            "current_password": "wrong_password",
            "new_password": "user67890",
        },
    )
    assert response.status_code == 400, response.text
    assert "Current password is incorrect" in response.json()["detail"]


async def test_admin_can_reset_user_password_and_old_token_becomes_invalid(client, db):
    admin = await seed_user(
        db,
        username="password_admin_reset@example.com",
        password="admin12345",
        role="admin",
        full_name="Password Reset Admin",
    )
    target = await seed_user(
        db,
        username="password_reset_target@example.com",
        password="user12345",
        role="user",
        full_name="Password Reset Target",
    )
    non_admin = await seed_user(
        db,
        username="password_reset_non_admin@example.com",
        password="user12345",
        role="user",
        full_name="Password Reset Non Admin",
    )

    admin_token = await login(client, admin.username, "admin12345")
    target_token = await login(client, target.username, "user12345")
    non_admin_token = await login(client, non_admin.username, "user12345")

    forbidden_reset = await client.patch(
        f"/api/v1/users/{target.id}/password",
        headers=auth_headers(non_admin_token),
        json={"new_password": "reset67890"},
    )
    assert forbidden_reset.status_code == 403, forbidden_reset.text

    reset_response = await client.patch(
        f"/api/v1/users/{target.id}/password",
        headers=auth_headers(admin_token),
        json={"new_password": "reset67890"},
    )
    assert reset_response.status_code == 200, reset_response.text
    assert reset_response.json()["detail"] == "Password updated successfully"

    stale_token_me = await client.get("/api/v1/auth/me", headers=auth_headers(target_token))
    assert stale_token_me.status_code == 401, stale_token_me.text

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"username": target.username, "password": "user12345"},
    )
    assert old_login.status_code == 401, old_login.text

    new_token = await login(client, target.username, "reset67890")
    new_me = await client.get("/api/v1/auth/me", headers=auth_headers(new_token))
    assert new_me.status_code == 200, new_me.text
    assert new_me.json()["username"] == target.username


async def test_admin_can_delete_user_non_admin_cannot(client, db):
    admin = await seed_user(
        db,
        username="delete_admin@example.com",
        password="admin12345",
        role="admin",
        full_name="Delete Admin",
    )
    target = await seed_user(
        db,
        username="delete_target@example.com",
        password="user12345",
        role="user",
        full_name="Delete Target",
    )
    non_admin = await seed_user(
        db,
        username="delete_non_admin@example.com",
        password="user12345",
        role="user",
        full_name="Delete Non Admin",
    )

    admin_token = await login(client, admin.username, "admin12345")
    target_token = await login(client, target.username, "user12345")
    non_admin_token = await login(client, non_admin.username, "user12345")

    forbidden_delete = await client.delete(
        f"/api/v1/users/{target.id}",
        headers=auth_headers(non_admin_token),
    )
    assert forbidden_delete.status_code == 403, forbidden_delete.text

    delete_response = await client.delete(
        f"/api/v1/users/{target.id}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204, delete_response.text

    get_deleted_response = await client.get(
        f"/api/v1/users/{target.id}",
        headers=auth_headers(admin_token),
    )
    assert get_deleted_response.status_code == 404, get_deleted_response.text

    deleted_user_login = await client.post(
        "/api/v1/auth/login",
        json={"username": target.username, "password": "user12345"},
    )
    assert deleted_user_login.status_code == 401, deleted_user_login.text

    stale_token_me = await client.get("/api/v1/auth/me", headers=auth_headers(target_token))
    assert stale_token_me.status_code == 401, stale_token_me.text

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


async def test_group_update_crud_access_matrix(client, db):
    owner_teacher = await seed_user(
        db,
        username="group_owner_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Group Owner Teacher",
    )
    other_teacher = await seed_user(
        db,
        username="group_other_teacher@example.com",
        password="teach123",
        role="teacher",
        full_name="Group Other Teacher",
    )
    admin = await seed_user(
        db,
        username="group_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Group Admin",
    )

    owner_token = await login(client, owner_teacher.username, "teach123")
    other_token = await login(client, other_teacher.username, "teach123")
    admin_token = await login(client, admin.username, "admin123")

    create_response = await client.post(
        "/api/v1/groups/",
        headers=auth_headers(owner_token),
        json={"name": "group-initial"},
    )
    assert create_response.status_code == 201, create_response.text
    group_id = create_response.json()["id"]

    owner_update_response = await client.patch(
        f"/api/v1/groups/{group_id}",
        headers=auth_headers(owner_token),
        json={"name": "group-owner-updated"},
    )
    assert owner_update_response.status_code == 200, owner_update_response.text
    assert owner_update_response.json()["name"] == "group-owner-updated"

    forbidden_update_response = await client.patch(
        f"/api/v1/groups/{group_id}",
        headers=auth_headers(other_token),
        json={"name": "group-forbidden"},
    )
    assert forbidden_update_response.status_code == 403, forbidden_update_response.text

    admin_update_response = await client.patch(
        f"/api/v1/groups/{group_id}",
        headers=auth_headers(admin_token),
        json={"name": "group-admin-updated"},
    )
    assert admin_update_response.status_code == 200, admin_update_response.text
    assert admin_update_response.json()["name"] == "group-admin-updated"


async def test_material_blocks_and_attachments_crud_access(client, db):
    owner_teacher = await seed_user(
        db,
        username="material_owner@example.com",
        password="teach123",
        role="teacher",
        full_name="Material Owner",
    )
    other_teacher = await seed_user(
        db,
        username="material_other@example.com",
        password="teach123",
        role="teacher",
        full_name="Material Other",
    )
    admin = await seed_user(
        db,
        username="material_admin@example.com",
        password="admin123",
        role="admin",
        full_name="Material Admin",
    )

    owner_token = await login(client, owner_teacher.username, "teach123")
    other_token = await login(client, other_teacher.username, "teach123")
    admin_token = await login(client, admin.username, "admin123")

    create_material_response = await client.post(
        "/api/v1/materials/",
        headers=auth_headers(owner_token),
        json={
            "title": "Material CRUD",
            "material_type": "lesson",
            "status": "draft",
            "description": "Material for block/attachment CRUD",
            "blocks": [
                {
                    "block_type": "text",
                    "title": "Initial block",
                    "body": "Initial body",
                    "order_index": 0,
                }
            ],
            "attachments": [],
        },
    )
    assert create_material_response.status_code == 201, create_material_response.text
    material_id = create_material_response.json()["id"]

    list_blocks_response = await client.get(
        f"/api/v1/materials/{material_id}/blocks",
        headers=auth_headers(owner_token),
    )
    assert list_blocks_response.status_code == 200, list_blocks_response.text
    blocks = list_blocks_response.json()
    assert len(blocks) == 1
    initial_block_id = blocks[0]["id"]

    create_block_response = await client.post(
        f"/api/v1/materials/{material_id}/blocks",
        headers=auth_headers(owner_token),
        json={
            "block_type": "documentation_link",
            "title": "Docs",
            "url": "https://example.com/docs",
            "order_index": 2,
        },
    )
    assert create_block_response.status_code == 201, create_block_response.text
    created_block = create_block_response.json()
    assert created_block["block_type"] == "documentation_link"
    created_block_id = created_block["id"]

    update_block_response = await client.patch(
        f"/api/v1/materials/{material_id}/blocks/{created_block_id}",
        headers=auth_headers(owner_token),
        json={"title": "Docs updated", "order_index": 3},
    )
    assert update_block_response.status_code == 200, update_block_response.text
    assert update_block_response.json()["title"] == "Docs updated"
    assert update_block_response.json()["order_index"] == 3

    forbidden_block_mutation_response = await client.patch(
        f"/api/v1/materials/{material_id}/blocks/{initial_block_id}",
        headers=auth_headers(other_token),
        json={"title": "Should fail"},
    )
    assert forbidden_block_mutation_response.status_code == 403, forbidden_block_mutation_response.text

    delete_block_response = await client.delete(
        f"/api/v1/materials/{material_id}/blocks/{created_block_id}",
        headers=auth_headers(owner_token),
    )
    assert delete_block_response.status_code == 204, delete_block_response.text

    create_attachment_response = await client.post(
        f"/api/v1/materials/{material_id}/attachments",
        headers=auth_headers(owner_token),
        json={
            "title": "Slides",
            "file_url": "https://example.com/slides.pdf",
            "file_kind": "pdf",
            "order_index": 1,
            "is_downloadable": True,
        },
    )
    assert create_attachment_response.status_code == 201, create_attachment_response.text
    attachment_id = create_attachment_response.json()["id"]

    update_attachment_response = await client.patch(
        f"/api/v1/materials/{material_id}/attachments/{attachment_id}",
        headers=auth_headers(owner_token),
        json={"title": "Slides v2", "is_downloadable": False},
    )
    assert update_attachment_response.status_code == 200, update_attachment_response.text
    assert update_attachment_response.json()["title"] == "Slides v2"
    assert update_attachment_response.json()["is_downloadable"] is False

    admin_update_attachment_response = await client.patch(
        f"/api/v1/materials/{material_id}/attachments/{attachment_id}",
        headers=auth_headers(admin_token),
        json={"order_index": 9},
    )
    assert admin_update_attachment_response.status_code == 200, admin_update_attachment_response.text
    assert admin_update_attachment_response.json()["order_index"] == 9

    forbidden_attachment_mutation_response = await client.delete(
        f"/api/v1/materials/{material_id}/attachments/{attachment_id}",
        headers=auth_headers(other_token),
    )
    assert forbidden_attachment_mutation_response.status_code == 403, forbidden_attachment_mutation_response.text

    owner_delete_attachment_response = await client.delete(
        f"/api/v1/materials/{material_id}/attachments/{attachment_id}",
        headers=auth_headers(owner_token),
    )
    assert owner_delete_attachment_response.status_code == 204, owner_delete_attachment_response.text

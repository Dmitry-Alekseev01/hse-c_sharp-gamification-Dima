import pytest
from fastapi import HTTPException

from app.models.user import User
from app.repositories import material_repo
from app.schemas.material import MaterialCreate, MaterialUpdate
from app.services import material_service

pytestmark = pytest.mark.asyncio


async def _seed_teacher(db, username: str = "material_service_teacher@example.com") -> User:
    teacher = User(
        username=username,
        password_hash="x",
        role="teacher",
        full_name="Material Service Teacher",
    )
    db.add(teacher)
    await db.flush()
    return teacher


async def test_update_material_allows_clearing_blocks_when_attachments_still_exist(db):
    teacher = await _seed_teacher(db, username="material_update_partial@example.com")
    material = await material_repo.create_material(
        db,
        title="Material with content",
        author_id=teacher.id,
        blocks=[
            {
                "block_type": "text",
                "title": "Intro",
                "body": "Body",
                "order_index": 0,
            }
        ],
        attachments=[
            {
                "title": "Slides",
                "file_url": "https://example.com/slides.pdf",
                "file_kind": "pdf",
                "order_index": 0,
                "is_downloadable": True,
            }
        ],
    )

    updated = await material_service.update_material(
        db,
        material.id,
        MaterialUpdate(blocks=[]),
        teacher,
    )

    assert len(updated.blocks) == 0
    assert len(updated.attachments) == 1


async def test_update_material_rejects_empty_content_after_replace(db):
    teacher = await _seed_teacher(db, username="material_update_empty@example.com")
    material = await material_repo.create_material(
        db,
        title="Material for empty-check",
        author_id=teacher.id,
        blocks=[
            {
                "block_type": "text",
                "title": "Intro",
                "body": "Body",
                "order_index": 0,
            }
        ],
        attachments=[],
    )

    with pytest.raises(HTTPException, match="at least one content source"):
        await material_service.update_material(
            db,
            material.id,
            MaterialUpdate(blocks=[], attachments=[]),
            teacher,
        )


async def test_create_material_rejects_text_block_without_body(db):
    teacher = await _seed_teacher(db, username="material_text_validation@example.com")
    payload = MaterialCreate(
        title="Invalid material",
        blocks=[
            {
                "block_type": "text",
                "title": "Broken text block",
                "body": "",
            }
        ],
        attachments=[],
    )

    with pytest.raises(HTTPException, match="requires non-empty body"):
        await material_service.create_material(db, payload, teacher)


async def test_create_material_rejects_documentation_link_without_url(db):
    teacher = await _seed_teacher(db, username="material_link_validation@example.com")
    payload = MaterialCreate(
        title="Invalid link material",
        blocks=[
            {
                "block_type": "documentation_link",
                "title": "Broken link block",
                "url": "",
            }
        ],
        attachments=[],
    )

    with pytest.raises(HTTPException, match="requires non-empty url"):
        await material_service.create_material(db, payload, teacher)

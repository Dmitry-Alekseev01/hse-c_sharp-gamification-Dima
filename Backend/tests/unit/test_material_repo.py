import pytest

pytestmark = pytest.mark.asyncio

from app.repositories import material_repo


@pytest.mark.asyncio
async def test_create_material_with_blocks_and_attachments(db):
    material = await material_repo.create_material(
        db,
        title="Transport Layer",
        material_type="lesson",
        status="published",
        blocks=[
            {
                "block_type": "text",
                "title": "Введение",
                "body": "Рассмотрим протоколы TCP и UDP.",
                "order_index": 0,
            },
            {
                "block_type": "video_link",
                "title": "Видеозапись",
                "url": "https://example.com/video",
                "order_index": 1,
            },
        ],
        attachments=[
            {
                "title": "Лекция 4",
                "file_url": "https://example.com/lecture4.pptx",
                "file_kind": "pptx",
                "order_index": 0,
                "is_downloadable": True,
            }
        ],
    )

    assert material.material_type == "lesson"
    assert material.status == "published"
    assert len(material.blocks) == 2
    assert material.blocks[0].block_type == "text"
    assert len(material.attachments) == 1
    assert material.attachments[0].file_kind == "pptx"


@pytest.mark.asyncio
async def test_update_material_replaces_blocks_and_attachments(db):
    material = await material_repo.create_material(
        db,
        title="Transport Layer",
        blocks=[{"block_type": "text", "body": "old", "order_index": 0}],
        attachments=[{"title": "Old", "file_url": "https://example.com/old.pdf"}],
    )

    updated = await material_repo.update_material(
        db,
        material.id,
        status="draft",
        blocks=[
            {"block_type": "text", "body": "new", "order_index": 0},
            {"block_type": "documentation_link", "title": "Docs", "url": "https://learn.microsoft.com", "order_index": 1},
        ],
        attachments=[
            {
                "title": "New",
                "file_url": "https://example.com/new.docx",
                "file_kind": "docx",
                "order_index": 0,
                "is_downloadable": True,
            }
        ],
    )

    assert updated is not None
    assert updated.status == "draft"
    assert len(updated.blocks) == 2
    assert updated.blocks[1].block_type == "documentation_link"
    assert len(updated.attachments) == 1
    assert updated.attachments[0].file_kind == "docx"

"""
Repository for Material entity.
"""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.material import Material
from app.models.material_attachment import MaterialAttachment
from app.models.material_block import MaterialBlock
from app.models.test_ import Test


def _material_load_options():
    return (
        selectinload(Material.tests),
        selectinload(Material.required_level),
        selectinload(Material.blocks),
        selectinload(Material.attachments),
    )


def _sync_material_blocks(material: Material, blocks: list[dict] | None) -> None:
    if blocks is None:
        return
    material.blocks = [
        MaterialBlock(
            block_type=block["block_type"],
            title=block.get("title"),
            body=block.get("body"),
            url=block.get("url"),
            order_index=int(block.get("order_index", 0)),
        )
        for block in blocks
    ]


def _sync_material_attachments(material: Material, attachments: list[dict] | None) -> None:
    if attachments is None:
        return
    material.attachments = [
        MaterialAttachment(
            title=attachment["title"],
            file_url=attachment["file_url"],
            file_kind=attachment.get("file_kind", "other"),
            order_index=int(attachment.get("order_index", 0)),
            is_downloadable=bool(attachment.get("is_downloadable", True)),
        )
        for attachment in attachments
    ]


async def get_material(session, material_id: int):
    q = select(Material).options(*_material_load_options()).where(Material.id == material_id)
    res = await session.execute(q)
    return res.scalars().first()


async def list_materials(session, limit: int = 100, offset: int = 0):
    q = select(Material).options(*_material_load_options()).limit(limit).offset(offset)
    res = await session.execute(q)
    return res.scalars().all()


async def create_material(
    session,
    title: str,
    description: str | None = None,
    author_id: int | None = None,
    required_level_id: int | None = None,
    related_test_ids: list[int] | None = None,
    material_type: str = "lesson",
    status: str = "published",
    blocks: list[dict] | None = None,
    attachments: list[dict] | None = None,
):
    obj = Material(
        title=title,
        material_type=material_type,
        status=status,
        description=description,
        author_id=author_id,
        required_level_id=required_level_id,
    )
    _sync_material_blocks(obj, blocks)
    _sync_material_attachments(obj, attachments)
    session.add(obj)
    await session.flush()

    if related_test_ids:
        tests = (
            await session.execute(select(Test).where(Test.id.in_(related_test_ids)))
        ).scalars().all()
        obj.tests = tests
        await session.flush()

    await session.refresh(obj)
    return await get_material(session, obj.id)


async def update_material(
    session,
    material_id: int,
    **changes,
):
    material = await get_material(session, material_id)
    if material is None:
        return None

    if "title" in changes:
        material.title = changes["title"]
    if "material_type" in changes:
        material.material_type = changes["material_type"]
    if "status" in changes:
        material.status = changes["status"]
    if "description" in changes:
        material.description = changes["description"]
    if "required_level_id" in changes:
        material.required_level_id = changes["required_level_id"]

    if "related_test_ids" in changes:
        related_test_ids = changes["related_test_ids"]
        tests = (
            await session.execute(select(Test).where(Test.id.in_(related_test_ids)))
        ).scalars().all() if related_test_ids else []
        material.tests = tests

    if "blocks" in changes:
        _sync_material_blocks(material, changes["blocks"])

    if "attachments" in changes:
        _sync_material_attachments(material, changes["attachments"])

    await session.flush()
    await session.refresh(material)
    return await get_material(session, material.id)


async def delete_material(session, material_id: int) -> bool:
    material = await get_material(session, material_id)
    if material is None:
        return False
    await session.delete(material)
    await session.flush()
    return True

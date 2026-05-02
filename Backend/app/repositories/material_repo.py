"""
Repository for Material entity.
"""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models.level import Level
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


async def count_visible_materials_for_user(
    session,
    *,
    role: str,
    total_points: float,
) -> int:
    stmt = select(func.count(Material.id))
    if role not in {"teacher", "admin"}:
        stmt = (
            stmt.select_from(Material)
            .outerjoin(Level, Material.required_level_id == Level.id)
            .where(
                or_(
                    Material.required_level_id.is_(None),
                    Level.id.is_(None),
                    Level.required_points <= float(total_points),
                )
            )
        )
    count = await session.scalar(stmt)
    return int(count or 0)


async def list_material_blocks(session, material_id: int):
    stmt = (
        select(MaterialBlock)
        .where(MaterialBlock.material_id == material_id)
        .order_by(MaterialBlock.order_index.asc(), MaterialBlock.id.asc())
    )
    res = await session.execute(stmt)
    return res.scalars().all()


async def get_material_block(session, block_id: int) -> MaterialBlock | None:
    return await session.get(MaterialBlock, block_id)


async def create_material_block(
    session,
    *,
    material_id: int,
    block_type: str,
    title: str | None = None,
    body: str | None = None,
    url: str | None = None,
    order_index: int = 0,
) -> MaterialBlock:
    block = MaterialBlock(
        material_id=material_id,
        block_type=block_type,
        title=title,
        body=body,
        url=url,
        order_index=order_index,
    )
    session.add(block)
    await session.flush()
    await session.refresh(block)
    return block


async def update_material_block(session, block_id: int, **changes) -> MaterialBlock | None:
    block = await get_material_block(session, block_id)
    if block is None:
        return None
    if "block_type" in changes:
        block.block_type = changes["block_type"]
    if "title" in changes:
        block.title = changes["title"]
    if "body" in changes:
        block.body = changes["body"]
    if "url" in changes:
        block.url = changes["url"]
    if "order_index" in changes:
        block.order_index = changes["order_index"]
    await session.flush()
    await session.refresh(block)
    return block


async def delete_material_block(session, block_id: int) -> bool:
    block = await get_material_block(session, block_id)
    if block is None:
        return False
    await session.delete(block)
    await session.flush()
    return True


async def list_material_attachments(session, material_id: int):
    stmt = (
        select(MaterialAttachment)
        .where(MaterialAttachment.material_id == material_id)
        .order_by(MaterialAttachment.order_index.asc(), MaterialAttachment.id.asc())
    )
    res = await session.execute(stmt)
    return res.scalars().all()


async def get_material_attachment(session, attachment_id: int) -> MaterialAttachment | None:
    return await session.get(MaterialAttachment, attachment_id)


async def create_material_attachment(
    session,
    *,
    material_id: int,
    title: str,
    file_url: str,
    file_kind: str = "other",
    order_index: int = 0,
    is_downloadable: bool = True,
) -> MaterialAttachment:
    attachment = MaterialAttachment(
        material_id=material_id,
        title=title,
        file_url=file_url,
        file_kind=file_kind,
        order_index=order_index,
        is_downloadable=is_downloadable,
    )
    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)
    return attachment


async def update_material_attachment(session, attachment_id: int, **changes) -> MaterialAttachment | None:
    attachment = await get_material_attachment(session, attachment_id)
    if attachment is None:
        return None
    if "title" in changes:
        attachment.title = changes["title"]
    if "file_url" in changes:
        attachment.file_url = changes["file_url"]
    if "file_kind" in changes:
        attachment.file_kind = changes["file_kind"]
    if "order_index" in changes:
        attachment.order_index = changes["order_index"]
    if "is_downloadable" in changes:
        attachment.is_downloadable = changes["is_downloadable"]
    await session.flush()
    await session.refresh(attachment)
    return attachment


async def delete_material_attachment(session, attachment_id: int) -> bool:
    attachment = await get_material_attachment(session, attachment_id)
    if attachment is None:
        return False
    await session.delete(attachment)
    await session.flush()
    return True


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

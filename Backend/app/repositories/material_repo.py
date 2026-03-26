"""
Repository for Material entity.
"""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.material import Material
from app.models.test_ import Test

async def get_material(session, material_id: int):
    q = select(Material).options(selectinload(Material.tests)).where(Material.id == material_id)
    res = await session.execute(q)
    return res.scalars().first()

async def list_materials(session, limit: int = 100, offset: int = 0):
    q = select(Material).options(selectinload(Material.tests)).limit(limit).offset(offset)
    res = await session.execute(q)
    return res.scalars().all()

async def create_material(
    session,
    title: str,
    content_text: str,
    description: str | None = None,
    content_url: str | None = None,
    video_url: str | None = None,
    author_id: int | None = None,
    related_test_ids: list[int] | None = None,
):
    obj = Material(
        title=title,
        description=description,
        content_text=content_text,
        content_url=content_url,
        video_url=video_url,
        author_id=author_id,
    )
    session.add(obj)
    await session.flush()
    if related_test_ids:
        tests = (
            await session.execute(select(Test).where(Test.id.in_(related_test_ids)))
        ).scalars().all()
        obj.tests = tests
        await session.flush()
    await session.refresh(obj)
    return obj


async def update_material(
    session,
    material_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    content_text: str | None = None,
    content_url: str | None = None,
    video_url: str | None = None,
    related_test_ids: list[int] | None = None,
):
    material = await get_material(session, material_id)
    if material is None:
        return None

    if title is not None:
        material.title = title
    if description is not None:
        material.description = description
    if content_text is not None:
        material.content_text = content_text
    if content_url is not None:
        material.content_url = content_url
    if video_url is not None:
        material.video_url = video_url
    if related_test_ids is not None:
        tests = (
            await session.execute(select(Test).where(Test.id.in_(related_test_ids)))
        ).scalars().all() if related_test_ids else []
        material.tests = tests

    await session.flush()
    await session.refresh(material)
    return material


async def delete_material(session, material_id: int) -> bool:
    material = await get_material(session, material_id)
    if material is None:
        return False
    await session.delete(material)
    await session.flush()
    return True

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import (
    get_manageable_material,
    get_user_level_context,
    get_visible_material,
    is_unlocked_material,
)
from app.api.deps import get_db
from app.cache.redis_cache import (
    MATERIALS_LIST_TTL,
    MATERIAL_DETAIL_TTL,
    NS_MATERIALS,
    NS_TESTS,
    NS_TEST_CONTENT,
    bump_cache_namespace,
    cache_key_material_detail,
    cache_key_material_list,
    get_cache_namespace_version,
    get,
    set,
)
from app.core.security import get_current_user, require_roles
from app.models.user import User
from app.repositories import material_repo
from app.schemas.material import (
    MaterialAttachmentCreate,
    MaterialAttachmentRead,
    MaterialAttachmentUpdate,
    MaterialBlockCreate,
    MaterialBlockRead,
    MaterialBlockUpdate,
    MaterialCreate,
    MaterialRead,
    MaterialUpdate,
)
from app.services import material_service

router = APIRouter()


@router.get("/", response_model=List[MaterialRead], status_code=status.HTTP_200_OK)
async def list_materials(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_points, level_id = await get_user_level_context(db, current_user)
    if current_user.role not in {"teacher", "admin"}:
        version = await get_cache_namespace_version(NS_MATERIALS)
        cache_key = cache_key_material_list(limit=limit, offset=offset, level_id=level_id, version=version)
        cached = await get(cache_key)
        if cached is not None:
            return cached

    items = await material_repo.list_materials(db, limit=limit, offset=offset)
    if current_user.role not in {"teacher", "admin"}:
        items = [
            item
            for item in items
            if await is_unlocked_material(db, current_user, item, total_points=total_points)
        ]
        payload = [MaterialRead.model_validate(item).model_dump(mode="json") for item in items]
        await set(cache_key, payload, ttl=MATERIALS_LIST_TTL)
    return items


@router.get("/{material_id}", response_model=MaterialRead, status_code=status.HTTP_200_OK)
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_points: float | None = None
    level_id = -1
    if current_user.role not in {"teacher", "admin"}:
        total_points, level_id = await get_user_level_context(db, current_user)
        version = await get_cache_namespace_version(NS_MATERIALS)
        cache_key = cache_key_material_detail(material_id, level_id=level_id, version=version)
        cached = await get(cache_key)
        if cached is not None:
            return cached

    material = await get_visible_material(db, material_id, current_user, total_points=total_points)
    if current_user.role not in {"teacher", "admin"}:
        payload = MaterialRead.model_validate(material).model_dump(mode="json")
        await set(cache_key, payload, ttl=MATERIAL_DETAIL_TTL)
    return material


@router.post("/", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    payload: MaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    material = await material_service.create_material(db, payload, current_user)
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return material


@router.patch("/{material_id}", response_model=MaterialRead, status_code=status.HTTP_200_OK)
async def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    material = await material_service.update_material(db, material_id, payload, current_user)
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    deleted = await material_repo.delete_material(db, material_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return {}


@router.get("/{material_id}/blocks", response_model=List[MaterialBlockRead], status_code=status.HTTP_200_OK)
async def list_material_blocks(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    return await material_repo.list_material_blocks(db, material_id)


@router.post("/{material_id}/blocks", response_model=MaterialBlockRead, status_code=status.HTTP_201_CREATED)
async def create_material_block(
    material_id: int,
    payload: MaterialBlockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    block = await material_repo.create_material_block(
        db,
        material_id=material_id,
        block_type=payload.block_type.value,
        title=payload.title,
        body=payload.body,
        url=payload.url,
        order_index=payload.order_index,
    )
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return block


@router.patch("/{material_id}/blocks/{block_id}", response_model=MaterialBlockRead, status_code=status.HTTP_200_OK)
async def update_material_block(
    material_id: int,
    block_id: int,
    payload: MaterialBlockUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    block = await material_repo.get_material_block(db, block_id)
    if block is None or block.material_id != material_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material block not found")
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if "block_type" in changes and changes["block_type"] is not None:
        changes["block_type"] = payload.block_type.value
    updated = await material_repo.update_material_block(db, block_id, **changes)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material block not found")
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return updated


@router.delete("/{material_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_block(
    material_id: int,
    block_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    block = await material_repo.get_material_block(db, block_id)
    if block is None or block.material_id != material_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material block not found")
    await material_repo.delete_material_block(db, block_id)
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return {}


@router.get("/{material_id}/attachments", response_model=List[MaterialAttachmentRead], status_code=status.HTTP_200_OK)
async def list_material_attachments(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    return await material_repo.list_material_attachments(db, material_id)


@router.post("/{material_id}/attachments", response_model=MaterialAttachmentRead, status_code=status.HTTP_201_CREATED)
async def create_material_attachment(
    material_id: int,
    payload: MaterialAttachmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    attachment = await material_repo.create_material_attachment(
        db,
        material_id=material_id,
        title=payload.title,
        file_url=payload.file_url,
        file_kind=payload.file_kind.value,
        order_index=payload.order_index,
        is_downloadable=payload.is_downloadable,
    )
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return attachment


@router.patch(
    "/{material_id}/attachments/{attachment_id}",
    response_model=MaterialAttachmentRead,
    status_code=status.HTTP_200_OK,
)
async def update_material_attachment(
    material_id: int,
    attachment_id: int,
    payload: MaterialAttachmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    attachment = await material_repo.get_material_attachment(db, attachment_id)
    if attachment is None or attachment.material_id != material_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material attachment not found")
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if "file_kind" in changes and changes["file_kind"] is not None:
        changes["file_kind"] = payload.file_kind.value
    updated = await material_repo.update_material_attachment(db, attachment_id, **changes)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material attachment not found")
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return updated


@router.delete("/{material_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_attachment(
    material_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    attachment = await material_repo.get_material_attachment(db, attachment_id)
    if attachment is None or attachment.material_id != material_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material attachment not found")
    await material_repo.delete_material_attachment(db, attachment_id)
    await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
    return {}

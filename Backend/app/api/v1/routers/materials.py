from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import get_manageable_material, get_manageable_test, get_user_level_context, get_visible_material, is_unlocked_material
from app.api.deps import get_db
from app.cache.redis_cache import (
    MATERIALS_LIST_TTL,
    MATERIAL_DETAIL_TTL,
    cache_key_material_detail,
    cache_key_material_list,
    delete_pattern,
    get,
    set,
)
from app.core.security import get_current_user, require_roles
from app.models.user import User
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate
from app.repositories import material_repo

router = APIRouter()


async def _validate_related_tests(
    db: AsyncSession,
    current_user: User,
    related_test_ids: list[int] | None,
) -> None:
    for test_id in {test_id for test_id in (related_test_ids or []) if test_id is not None}:
        await get_manageable_test(db, test_id, current_user)


@router.get("/", response_model=List[MaterialRead], status_code=status.HTTP_200_OK)
async def list_materials(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _, level_id = await get_user_level_context(db, current_user)
    if current_user.role not in {"teacher", "admin"}:
        cache_key = cache_key_material_list(limit=limit, offset=offset, level_id=level_id)
        cached = await get(cache_key)
        if cached is not None:
            return cached

    items = await material_repo.list_materials(db, limit=limit, offset=offset)
    if current_user.role not in {"teacher", "admin"}:
        items = [item for item in items if await is_unlocked_material(db, current_user, item)]
        payload = [MaterialRead.model_validate(item).model_dump(mode="json") for item in items]
        await set(cache_key, payload, ttl=MATERIALS_LIST_TTL)
    return items


@router.get("/{material_id}", response_model=MaterialRead, status_code=status.HTTP_200_OK)
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _, level_id = await get_user_level_context(db, current_user)
    if current_user.role not in {"teacher", "admin"}:
        cache_key = cache_key_material_detail(material_id, level_id=level_id)
        cached = await get(cache_key)
        if cached is not None:
            return cached

    m = await get_visible_material(db, material_id, current_user)
    if current_user.role not in {"teacher", "admin"}:
        payload = MaterialRead.model_validate(m).model_dump(mode="json")
        await set(cache_key, payload, ttl=MATERIAL_DETAIL_TTL)
    return m


@router.post("/", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    payload: MaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    """
    Create material. For now no auth check is performed here — consider adding later.
    """
    try:
        await _validate_related_tests(db, current_user, payload.related_test_ids)
        m = await material_repo.create_material(
            db,
            title=payload.title,
            content_text=payload.content_text,
            description=payload.description,
            content_url=payload.content_url,
            video_url=payload.video_url,
            author_id=current_user.id,
            required_level_id=payload.required_level_id,
            related_test_ids=payload.related_test_ids,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await delete_pattern("materials:*")
    await delete_pattern("tests:list:*")
    await delete_pattern("tests:detail:*")
    await delete_pattern("tests:content:*")
    return m


@router.patch("/{material_id}", response_model=MaterialRead, status_code=status.HTTP_200_OK)
async def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_material(db, material_id, current_user)
    await _validate_related_tests(db, current_user, payload.related_test_ids)
    material = await material_repo.update_material(db, material_id, **payload.model_dump(exclude_unset=True))
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await delete_pattern("materials:*")
    await delete_pattern("tests:list:*")
    await delete_pattern("tests:detail:*")
    await delete_pattern("tests:content:*")
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
    await delete_pattern("materials:*")
    await delete_pattern("tests:list:*")
    await delete_pattern("tests:detail:*")
    await delete_pattern("tests:content:*")
    return {}

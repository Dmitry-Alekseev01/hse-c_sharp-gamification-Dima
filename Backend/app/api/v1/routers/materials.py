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
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate
from app.services import material_service

router = APIRouter()


@router.get("/", response_model=List[MaterialRead], status_code=status.HTTP_200_OK)
async def list_materials(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _, level_id = await get_user_level_context(db, current_user)
    if current_user.role not in {"teacher", "admin"}:
        version = await get_cache_namespace_version(NS_MATERIALS)
        cache_key = cache_key_material_list(limit=limit, offset=offset, level_id=level_id, version=version)
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
        version = await get_cache_namespace_version(NS_MATERIALS)
        cache_key = cache_key_material_detail(material_id, level_id=level_id, version=version)
        cached = await get(cache_key)
        if cached is not None:
            return cached

    material = await get_visible_material(db, material_id, current_user)
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

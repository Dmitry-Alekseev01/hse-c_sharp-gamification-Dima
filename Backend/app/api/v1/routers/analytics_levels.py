from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_user, require_roles
from app.models.user import User
from app.schemas.level import LevelCreate, LevelRead, LevelUpdate
from app.services import level_admin_service

router = APIRouter()


@router.post("/levels", response_model=LevelRead, status_code=status.HTTP_201_CREATED)
async def create_level(
    payload: LevelCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return await level_admin_service.create_level(db, payload)


@router.get("/levels", response_model=List[LevelRead], status_code=status.HTTP_200_OK)
async def list_levels(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Return configured levels (id, name, required_points, description).
    """
    return await level_admin_service.list_levels(db)


@router.get("/levels/{level_id}", response_model=LevelRead, status_code=status.HTTP_200_OK)
async def get_level(
    level_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await level_admin_service.get_level(db, level_id)


@router.patch("/levels/{level_id}", response_model=LevelRead, status_code=status.HTTP_200_OK)
async def update_level(
    level_id: int,
    payload: LevelUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return await level_admin_service.update_level(db, level_id, payload)


@router.delete("/levels/{level_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_level(
    level_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    await level_admin_service.delete_level(db, level_id)
    return {}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories import level_repo
from app.schemas.level import LevelRead

router = APIRouter()


@router.get("/", response_model=list[LevelRead], status_code=200)
async def list_levels(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await level_repo.list_levels(db)


@router.get("/by-points", response_model=LevelRead, status_code=200)
async def get_current_level(
    points: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    lvl = await level_repo.get_current_level_for_points(db, points)
    if not lvl:
        raise HTTPException(status_code=404, detail="Level not found")
    return lvl

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_user, require_roles
from app.models.user import User
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate
from app.repositories import material_repo

router = APIRouter()


@router.get("/", response_model=List[MaterialRead], status_code=status.HTTP_200_OK)
async def list_materials(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    List published materials (or all, depending on repo implementation).
    """
    items = await material_repo.list_materials(db, limit=limit, offset=offset)
    return items


@router.get("/{material_id}", response_model=MaterialRead, status_code=status.HTTP_200_OK)
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Get a single material by id.
    """
    m = await material_repo.get_material(db, material_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
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
        m = await material_repo.create_material(
            db,
            title=payload.title,
            content_text=payload.content_text,
            description=payload.description,
            content_url=payload.content_url,
            video_url=payload.video_url,
            author_id=current_user.id,
            related_test_ids=payload.related_test_ids,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return m


@router.patch("/{material_id}", response_model=MaterialRead, status_code=status.HTTP_200_OK)
async def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    material = await material_repo.update_material(db, material_id, **payload.model_dump(exclude_unset=True))
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    deleted = await material_repo.delete_material(db, material_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    return {}

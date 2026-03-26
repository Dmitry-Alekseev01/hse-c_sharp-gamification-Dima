from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import require_roles
from app.models.user import User
from app.repositories import group_repo
from app.schemas.group import GroupCreate, GroupRead, GroupDetailRead


router = APIRouter()


def _serialize_group(group) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "teacher_id": group.teacher_id,
        "members": [
            {
                "user_id": membership.user_id,
                "username": membership.user.username if membership.user else "",
                "full_name": membership.user.full_name if membership.user else None,
            }
            for membership in group.memberships
        ],
    }


async def _get_managed_group(db: AsyncSession, group_id: int, current_user: User):
    group = await group_repo.get_group(db, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if current_user.role != "admin" and group.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return group


@router.get("/", response_model=list[GroupDetailRead], status_code=status.HTTP_200_OK)
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    groups = (
        await group_repo.list_all_groups(db)
        if current_user.role == "admin"
        else await group_repo.list_groups_for_teacher(db, current_user.id)
    )
    return [_serialize_group(group) for group in groups]


@router.post("/", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = await group_repo.create_group(db, payload.name, current_user.id)
    return group


@router.get("/{group_id}", response_model=GroupDetailRead, status_code=status.HTTP_200_OK)
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = await _get_managed_group(db, group_id, current_user)
    return _serialize_group(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await _get_managed_group(db, group_id, current_user)
    await group_repo.delete_group(db, group_id)
    return {}


@router.post("/{group_id}/members/{user_id}", response_model=GroupDetailRead, status_code=status.HTTP_200_OK)
async def add_group_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = await _get_managed_group(db, group_id, current_user)
    try:
        await group_repo.add_user_to_group(db, group, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    refreshed = await group_repo.get_group(db, group_id)
    return _serialize_group(refreshed)


@router.delete("/{group_id}/members/{user_id}", response_model=GroupDetailRead, status_code=status.HTTP_200_OK)
async def remove_group_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = await _get_managed_group(db, group_id, current_user)
    removed = await group_repo.remove_user_from_group(db, group, user_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    refreshed = await group_repo.get_group(db, group_id)
    return _serialize_group(refreshed)

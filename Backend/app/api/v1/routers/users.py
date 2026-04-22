from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_user, require_roles
from app.schemas.user import AdminUserCreate, UserProfileUpdate, UserRead, UserRoleUpdate
from app.services import user_service
from app.repositories import user_repo
from app.models.user import User as UserModel

router = APIRouter()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    _: UserModel = Depends(require_roles("admin")),
):
    """
    Register a new user.
    Uses user_service.register_user which should validate uniqueness, hash password, etc.
    """
    try:
        user = await user_service.register_user(
            db,
            payload.username,
            payload.password,
            payload.full_name,
            role=payload.role,
        )
    except ValueError as e:
        # service may raise ValueError for validation (e.g. username exists)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")
    return user


@router.get("/", response_model=List[UserRead])
async def list_users(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: UserModel = Depends(require_roles("admin")),
):
    """
    List users (basic).
    """
    users = await user_repo.list_users(db, limit=limit)
    return users


@router.patch("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
async def update_my_profile(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        user = await user_service.update_user_profile(
            db,
            current_user.id,
            username=payload.username,
            full_name=payload.full_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return user


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Get user by id. Returns 404 if not found.
    """
    user = await db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


@router.patch("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def update_user_profile_by_admin(
    user_id: int,
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserModel = Depends(require_roles("admin")),
):
    try:
        user = await user_service.update_user_profile(
            db,
            user_id,
            username=payload.username,
            full_name=payload.full_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return user


@router.patch("/{user_id}/role", response_model=UserRead, status_code=status.HTTP_200_OK)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserModel = Depends(require_roles("admin")),
):
    user = await user_repo.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = payload.role
    await db.flush()
    await db.refresh(user)
    return user

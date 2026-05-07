from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_user, invalidate_auth_user_cache, require_roles
from app.schemas.user import (
    AdminUserCreate,
    AdminUserPasswordReset,
    PasswordChangeRead,
    UserPasswordChange,
    UserProfileUpdate,
    UserRead,
    UserRoleUpdate,
)
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
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username already exists") from e
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


@router.patch("/me/password", response_model=PasswordChangeRead, status_code=status.HTTP_200_OK)
async def change_my_password(
    payload: UserPasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        await user_service.change_user_password(
            db,
            current_user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PasswordChangeRead(detail="Password updated successfully")


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
    await invalidate_auth_user_cache(user.username)
    return user


@router.patch("/{user_id}/password", response_model=PasswordChangeRead, status_code=status.HTTP_200_OK)
async def reset_user_password_by_admin(
    user_id: int,
    payload: AdminUserPasswordReset,
    db: AsyncSession = Depends(get_db),
    current_admin: UserModel = Depends(require_roles("admin")),
):
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /api/v1/users/me/password to change your own password",
        )
    try:
        await user_service.admin_reset_user_password(
            db,
            user_id,
            new_password=payload.new_password,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PasswordChangeRead(detail="Password updated successfully")


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: UserModel = Depends(require_roles("admin")),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot delete own account")
    try:
        await user_service.delete_user(db, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {}

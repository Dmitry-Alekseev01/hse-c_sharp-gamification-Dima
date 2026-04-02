from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.test_ import Test
from app.models.user import User
from app.repositories import material_repo, test_repo


def can_manage_test(current_user: User, test: Test) -> bool:
    return current_user.role == "admin" or (
        current_user.role == "teacher" and test.author_id == current_user.id
    )


def can_manage_material(current_user: User, material: Material) -> bool:
    return current_user.role == "admin" or (
        current_user.role == "teacher" and material.author_id == current_user.id
    )


async def get_test_or_404(db: AsyncSession, test_id: int) -> Test:
    test = await test_repo.get_test(db, test_id)
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


async def get_material_or_404(db: AsyncSession, material_id: int) -> Material:
    material = await material_repo.get_material(db, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    return material


async def get_manageable_test(db: AsyncSession, test_id: int, current_user: User) -> Test:
    test = await get_test_or_404(db, test_id)
    if not can_manage_test(current_user, test):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return test


async def get_manageable_material(db: AsyncSession, material_id: int, current_user: User) -> Material:
    material = await get_material_or_404(db, material_id)
    if not can_manage_material(current_user, material):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return material


async def get_visible_test(db: AsyncSession, test_id: int, current_user: User) -> Test:
    test = await get_test_or_404(db, test_id)
    if test.published or can_manage_test(current_user, test):
        return test
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

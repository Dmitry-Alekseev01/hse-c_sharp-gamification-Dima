from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.test_ import Test
from app.models.user import User
from app.repositories import analytics_repo, level_repo, material_repo, test_repo


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
    if can_manage_test(current_user, test):
        return test
    if test.published and await is_unlocked_test(db, current_user, test):
        return test
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")


async def get_visible_material(db: AsyncSession, material_id: int, current_user: User) -> Material:
    material = await get_material_or_404(db, material_id)
    if can_manage_material(current_user, material):
        return material
    if await is_unlocked_material(db, current_user, material):
        return material
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")


async def get_user_level_context(db: AsyncSession, current_user: User) -> tuple[float, int]:
    if current_user.role in {"teacher", "admin"}:
        return 0.0, -1
    analytics = await analytics_repo.get_user_analytics(db, current_user.id)
    total_points = float(analytics.total_points or 0.0) if analytics is not None else 0.0
    level_id = int(analytics.current_level_id or 0) if analytics is not None else 0
    return total_points, level_id


async def ensure_level_exists_or_400(db: AsyncSession, level_id: int | None) -> None:
    if level_id is None:
        return
    level = await level_repo.get_level_by_id(db, level_id)
    if level is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="required_level_id does not reference an existing level",
        )


async def is_unlocked_test(db: AsyncSession, current_user: User, test: Test) -> bool:
    if current_user.role in {"teacher", "admin"}:
        return True
    if test.required_level is None:
        return True
    total_points, _ = await get_user_level_context(db, current_user)
    return float(test.required_level.required_points or 0.0) <= total_points


async def is_unlocked_material(db: AsyncSession, current_user: User, material: Material) -> bool:
    if current_user.role in {"teacher", "admin"}:
        return True
    if material.required_level is None:
        return True
    total_points, _ = await get_user_level_context(db, current_user)
    return float(material.required_level.required_points or 0.0) <= total_points

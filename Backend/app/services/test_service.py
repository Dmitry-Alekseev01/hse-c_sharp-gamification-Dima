from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import (
    ensure_level_exists_or_400,
    get_manageable_material,
    get_manageable_test,
    get_visible_test,
)
from app.models.user import User
from app.repositories import test_repo
from app.schemas.test_ import TestCreate, TestUpdate


async def validate_related_materials(
    db: AsyncSession,
    current_user: User,
    material_id: int | None,
    material_ids: list[int] | None,
) -> None:
    candidate_ids = []
    if material_id is not None:
        candidate_ids.append(material_id)
    if material_ids:
        candidate_ids.extend(material_ids)

    for candidate_id in {candidate_id for candidate_id in candidate_ids if candidate_id is not None}:
        await get_manageable_material(db, candidate_id, current_user)


async def create_test(
    db: AsyncSession,
    payload: TestCreate,
    current_user: User,
):
    await ensure_level_exists_or_400(db, payload.required_level_id)
    await validate_related_materials(db, current_user, payload.material_id, payload.material_ids)
    return await test_repo.create_test(
        db,
        title=payload.title,
        description=payload.description,
        time_limit_minutes=payload.time_limit_minutes,
        max_score=payload.max_score,
        published=payload.published,
        material_id=payload.material_id,
        material_ids=payload.material_ids,
        deadline=payload.deadline,
        author_id=current_user.id,
        required_level_id=payload.required_level_id,
    )


async def update_test(
    db: AsyncSession,
    test_id: int,
    payload: TestUpdate,
    current_user: User,
):
    await get_manageable_test(db, test_id, current_user)
    if "required_level_id" in payload.model_fields_set:
        await ensure_level_exists_or_400(db, payload.required_level_id)
    await validate_related_materials(db, current_user, payload.material_id, payload.material_ids)
    test = await test_repo.update_test(db, test_id, **payload.model_dump(exclude_unset=True))
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


async def get_test_or_summary_access(db: AsyncSession, test_id: int, current_user: User):
    test = await get_visible_test(db, test_id, current_user)
    if current_user.role == "teacher":
        if test.author_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        if not test.published:
            await get_manageable_test(db, test_id, current_user)
    return test

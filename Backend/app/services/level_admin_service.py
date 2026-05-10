from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_cache import NS_LEVELS, NS_MATERIALS, NS_TESTS, bump_cache_namespace
from app.repositories import level_repo
from app.schemas.level import LevelCreate, LevelUpdate


def _validate_level_constraints(*, required_points: int) -> None:
    if required_points < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="required_points must be >= 0")


async def _invalidate_level_related_caches() -> None:
    try:
        await bump_cache_namespace(NS_LEVELS, NS_TESTS, NS_MATERIALS)
    except Exception:
        # Cache invalidation failure must not break level CRUD.
        pass


async def create_level(session: AsyncSession, payload: LevelCreate):
    _validate_level_constraints(required_points=payload.required_points)

    existing_by_name = await level_repo.get_level_by_name(session, payload.name)
    if existing_by_name is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Level name already exists")

    existing_by_required_points = await level_repo.get_level_by_required_points(session, payload.required_points)
    if existing_by_required_points is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="required_points must be unique")

    try:
        level = await level_repo.create_level(
            session,
            name=payload.name,
            required_points=payload.required_points,
            description=payload.description,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create level") from exc

    await _invalidate_level_related_caches()
    return level


async def list_levels(session: AsyncSession):
    return await level_repo.list_levels(session)


async def get_level(session: AsyncSession, level_id: int):
    level = await level_repo.get_level_by_id(session, level_id)
    if level is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found")
    return level


async def update_level(session: AsyncSession, level_id: int, payload: LevelUpdate):
    level = await level_repo.get_level_by_id(session, level_id)
    if level is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be provided")

    next_name = changes.get("name", level.name)
    if next_name != level.name:
        existing_by_name = await level_repo.get_level_by_name(session, next_name)
        if existing_by_name is not None and existing_by_name.id != level_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Level name already exists")

    next_required_points = changes.get("required_points", level.required_points)
    _validate_level_constraints(required_points=next_required_points)
    if next_required_points != level.required_points:
        existing_by_required_points = await level_repo.get_level_by_required_points(session, next_required_points)
        if existing_by_required_points is not None and existing_by_required_points.id != level_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="required_points must be unique")

    try:
        updated = await level_repo.update_level(session, level_id, **changes)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to update level") from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found")

    await _invalidate_level_related_caches()
    return updated


async def delete_level(session: AsyncSession, level_id: int) -> None:
    try:
        deleted = await level_repo.delete_level(session, level_id)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Level is referenced by existing tests/materials",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found")

    await _invalidate_level_related_caches()

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import ensure_level_exists_or_400, get_manageable_material, get_manageable_test
from app.models.user import User
from app.repositories import material_repo
from app.schemas.material import MaterialCreate, MaterialUpdate


def ensure_material_has_content(payload: MaterialCreate | MaterialUpdate) -> None:
    has_content = bool(getattr(payload, "blocks", None)) or bool(getattr(payload, "attachments", None))
    if not has_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material must contain at least one content source: block or attachment",
        )


async def validate_related_tests(
    db: AsyncSession,
    current_user: User,
    related_test_ids: list[int] | None,
) -> None:
    for test_id in {test_id for test_id in (related_test_ids or []) if test_id is not None}:
        await get_manageable_test(db, test_id, current_user)


async def create_material(
    db: AsyncSession,
    payload: MaterialCreate,
    current_user: User,
):
    ensure_material_has_content(payload)
    await ensure_level_exists_or_400(db, payload.required_level_id)
    await validate_related_tests(db, current_user, payload.related_test_ids)
    try:
        return await material_repo.create_material(
            db,
            title=payload.title,
            material_type=payload.material_type.value,
            status=payload.status.value,
            description=payload.description,
            author_id=current_user.id,
            required_level_id=payload.required_level_id,
            related_test_ids=payload.related_test_ids,
            blocks=[block.model_dump(mode="json") for block in payload.blocks],
            attachments=[attachment.model_dump(mode="json") for attachment in payload.attachments],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


async def update_material(
    db: AsyncSession,
    material_id: int,
    payload: MaterialUpdate,
    current_user: User,
):
    await get_manageable_material(db, material_id, current_user)
    if any(field in payload.model_fields_set for field in {"blocks", "attachments"}):
        ensure_material_has_content(payload)
    if "required_level_id" in payload.model_fields_set:
        await ensure_level_exists_or_400(db, payload.required_level_id)
    await validate_related_tests(db, current_user, payload.related_test_ids)
    material = await material_repo.update_material(
        db,
        material_id,
        **payload.model_dump(exclude_unset=True, mode="json"),
    )
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    return material

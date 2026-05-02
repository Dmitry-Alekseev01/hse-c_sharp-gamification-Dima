from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import ensure_level_exists_or_400, get_manageable_material, get_manageable_test
from app.core.material_taxonomy import MaterialBlockType
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


def ensure_material_has_content_after_update(existing_blocks: int, existing_attachments: int, payload: MaterialUpdate) -> None:
    next_blocks = len(payload.blocks or []) if "blocks" in payload.model_fields_set else existing_blocks
    next_attachments = (
        len(payload.attachments or []) if "attachments" in payload.model_fields_set else existing_attachments
    )
    if next_blocks == 0 and next_attachments == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material must contain at least one content source: block or attachment",
        )


def validate_material_blocks(blocks, *, field_name: str = "blocks") -> None:
    for index, block in enumerate(blocks or [], start=1):
        if block.block_type in {MaterialBlockType.TEXT, MaterialBlockType.CODE_EXAMPLE}:
            if not (block.body or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field_name}[{index}] requires non-empty body for block_type={block.block_type.value}",
                )
        if block.block_type in {MaterialBlockType.DOCUMENTATION_LINK, MaterialBlockType.VIDEO_LINK}:
            if not (block.url or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field_name}[{index}] requires non-empty url for block_type={block.block_type.value}",
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
    validate_material_blocks(payload.blocks)
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
    material = await get_manageable_material(db, material_id, current_user)
    if any(field in payload.model_fields_set for field in {"blocks", "attachments"}):
        ensure_material_has_content_after_update(len(material.blocks), len(material.attachments), payload)
    if "blocks" in payload.model_fields_set:
        validate_material_blocks(payload.blocks)
    if "required_level_id" in payload.model_fields_set:
        await ensure_level_exists_or_400(db, payload.required_level_id)
    await validate_related_tests(db, current_user, payload.related_test_ids)
    updated_material = await material_repo.update_material(
        db,
        material_id,
        **payload.model_dump(exclude_unset=True, mode="json"),
    )
    if updated_material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    return updated_material

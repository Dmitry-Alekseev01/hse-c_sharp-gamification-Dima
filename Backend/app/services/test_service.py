from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import (
    ensure_level_exists_or_400,
    get_manageable_material,
    get_manageable_test,
    get_visible_test,
)
from app.models.user import User
from app.repositories import question_repo, test_repo
from app.schemas.test_content import TestContentWrite
from app.schemas.test_ import TestCreate, TestUpdate


async def validate_related_materials(
    db: AsyncSession,
    current_user: User,
    material_ids: list[int] | None,
) -> None:
    for candidate_id in {candidate_id for candidate_id in (material_ids or []) if candidate_id is not None}:
        await get_manageable_material(db, candidate_id, current_user)


async def create_test(
    db: AsyncSession,
    payload: TestCreate,
    current_user: User,
):
    await ensure_level_exists_or_400(db, payload.required_level_id)
    await validate_related_materials(db, current_user, payload.material_ids)
    return await test_repo.create_test(
        db,
        title=payload.title,
        description=payload.description,
        time_limit_minutes=payload.time_limit_minutes,
        max_score=payload.max_score,
        max_attempts=payload.max_attempts,
        published=payload.published,
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
    await validate_related_materials(db, current_user, payload.material_ids)
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


def _validate_test_content_payload(payload: TestContentWrite) -> None:
    for index, question in enumerate(payload.questions, start=1):
        if question.is_open_answer and question.choices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question #{index}: open-answer question must not include choices",
            )
        if not question.is_open_answer:
            if len(question.choices) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Question #{index}: closed question must include at least 2 choices",
                )
            correct_choices = sum(1 for choice in question.choices if choice.is_correct)
            if correct_choices < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Question #{index}: closed question must include at least 1 correct choice",
                )


async def replace_test_content(
    db: AsyncSession,
    *,
    test_id: int,
    payload: TestContentWrite,
    current_user: User,
):
    test = await get_manageable_test(db, test_id, current_user)
    _validate_test_content_payload(payload)

    await question_repo.delete_questions_for_test(db, test_id)
    for question in payload.questions:
        await question_repo.create_question_with_choices(
            db,
            test_id=test_id,
            text=question.text,
            points=question.points,
            is_open_answer=question.is_open_answer,
            material_urls=question.material_urls,
            choices=[choice.model_dump() for choice in question.choices] if question.choices else None,
        )

    questions = await question_repo.list_questions_for_test(db, test_id=test_id, limit=500, offset=0)
    return test, questions

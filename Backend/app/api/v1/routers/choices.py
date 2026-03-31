from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.cache.redis_cache import delete_pattern
from app.models.choice import Choice
from app.core.security import get_current_user, require_roles
from app.models.question import Question
from app.models.user import User
from app.schemas.question import ChoiceCreate, ChoiceRead, ChoiceTeacherRead
from app.repositories import choice_repo, test_repo

router = APIRouter()


@router.get("/question/{question_id}", response_model=List[ChoiceRead], status_code=status.HTTP_200_OK)
async def list_choices(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = await db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    test = await test_repo.get_test(db, question.test_id)
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.published and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    items = await choice_repo.list_choices_for_question(db, question_id)
    return items


@router.post("/", response_model=ChoiceTeacherRead, status_code=status.HTTP_201_CREATED)
async def create_choice(
    payload: ChoiceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    if payload.question_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question_id is required")
    question = await db.get(Question, payload.question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    ch = await choice_repo.create_choice(
        db,
        question_id=payload.question_id,
        value=payload.value,
        ordinal=payload.ordinal,
        is_correct=payload.is_correct,
    )
    await delete_pattern(f"questions:test:{question.test_id}:*")
    await delete_pattern(f"tests:content:{question.test_id}")
    return ch


@router.delete("/{choice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_choice(
    choice_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    choice = await db.get(Choice, choice_id)
    await choice_repo.delete_choice(db, choice_id)
    if choice is not None:
        question = await db.get(Question, choice.question_id)
        if question is not None:
            await delete_pattern(f"questions:test:{question.test_id}:*")
            await delete_pattern(f"tests:content:{question.test_id}")
    return {}

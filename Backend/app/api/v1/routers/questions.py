from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import get_manageable_test, get_visible_test
from app.api.deps import get_db
from app.cache.redis_cache import (
    QUESTION_LIST_TTL,
    cache_key_question_list,
    delete_pattern,
    get,
    set,
)
from app.core.security import get_current_user, require_roles
from app.models.user import User
from app.schemas.question import QuestionCreate, QuestionRead, QuestionTeacherRead, QuestionUpdate
from app.repositories import question_repo, test_repo

router = APIRouter()


@router.post("/", response_model=QuestionTeacherRead, status_code=status.HTTP_201_CREATED)
async def create_question(
    payload: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    """
    Create a question. payload may include 'choices' list (value, ordinal, is_correct).
    """
    await get_manageable_test(db, payload.test_id, current_user)
    q = await question_repo.create_question_with_choices(
        db,
        test_id=payload.test_id,
        text=payload.text,
        points=payload.points,
        is_open_answer=payload.is_open_answer,
        material_urls=payload.material_urls,
        choices=[c.model_dump() for c in (payload.choices or [])] if payload.choices else None,
    )
    await delete_pattern(f"questions:test:*:{payload.test_id}:*")
    await delete_pattern(f"tests:content:*:{payload.test_id}")
    await delete_pattern(f"test:{payload.test_id}:summary*")
    return q


@router.get("/test/{test_id}", response_model=List[QuestionRead], status_code=status.HTTP_200_OK)
async def list_questions_for_test(
    test_id: int,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = await get_visible_test(db, test_id, current_user)

    cache_key = cache_key_question_list(test_id=test_id, limit=limit, offset=offset)
    if test.published:
        cached = await get(cache_key)
        if cached is not None:
            return cached

    qs = await question_repo.list_questions_for_test(db, test_id=test_id, limit=limit, offset=offset)
    if test.published:
        payload = [QuestionRead.model_validate(q).model_dump(mode="json") for q in qs]
        await set(cache_key, payload, ttl=QUESTION_LIST_TTL)
    return qs


@router.get("/{question_id}", response_model=QuestionRead, status_code=status.HTTP_200_OK)
async def get_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await question_repo.get_question_with_choices(db, question_id)
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    await get_visible_test(db, q.test_id, current_user)
    return q


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    question = await question_repo.get_question_with_choices(db, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    test_id = question.test_id if question is not None else None
    await get_manageable_test(db, question.test_id, current_user)
    await question_repo.delete_question(db, question_id)
    if test_id is not None:
        await delete_pattern(f"questions:test:*:{test_id}:*")
        await delete_pattern(f"tests:content:*:{test_id}")
        await delete_pattern(f"test:{test_id}:summary*")
    return {}


@router.patch("/{question_id}", response_model=QuestionTeacherRead, status_code=status.HTTP_200_OK)
async def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    question = await question_repo.get_question_with_choices(db, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    await get_manageable_test(db, question.test_id, current_user)
    updated = await question_repo.update_question(db, question_id, **payload.model_dump(exclude_unset=True))
    await delete_pattern(f"questions:test:*:{question.test_id}:*")
    await delete_pattern(f"tests:content:*:{question.test_id}")
    await delete_pattern(f"test:{question.test_id}:summary*")
    return updated

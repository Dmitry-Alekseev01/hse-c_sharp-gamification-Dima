from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.cache.redis_cache import (
    TEST_CONTENT_TTL,
    TESTS_LIST_TTL,
    TEST_DETAIL_TTL,
    TEST_SUMMARY_TTL,
    cache_key_test_content,
    cache_key_test_detail,
    cache_key_test_list,
    cache_key_test_summary,
    delete_pattern,
    get,
    set,
)
from app.core.security import get_current_user, require_roles
from app.models.user import User
from app.schemas.question import QuestionRead
from app.schemas.test_ import TestCreate, TestRead, TestUpdate
from app.schemas.analytics import TestSummary
from app.schemas.test_attempt import TestAttemptRead
from app.schemas.test_content import TestContentRead
from app.repositories import analytics_repo, test_repo, test_attempt_repo
from app.repositories import question_repo

router = APIRouter()


@router.get("/", response_model=List[TestRead], status_code=status.HTTP_200_OK)
async def list_tests(
    published_only: bool = True,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not published_only and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if published_only:
        cache_key = cache_key_test_list(published_only=published_only, limit=limit)
        cached = await get(cache_key)
        if cached is not None:
            return cached

    items = await test_repo.list_tests(db, published_only=published_only, limit=limit)
    if published_only:
        payload = [TestRead.model_validate(item).model_dump(mode="json") for item in items]
        await set(cache_key, payload, ttl=TESTS_LIST_TTL)
    return items


@router.get("/{test_id}", response_model=TestRead, status_code=status.HTTP_200_OK)
async def get_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"teacher", "admin"}:
        cache_key = cache_key_test_detail(test_id)
        cached = await get(cache_key)
        if cached is not None:
            return cached

    t = await test_repo.get_test(db, test_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not t.published and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if t.published:
        payload = TestRead.model_validate(t).model_dump(mode="json")
        await set(cache_key_test_detail(test_id), payload, ttl=TEST_DETAIL_TTL)
    return t


@router.post("/", response_model=TestRead, status_code=status.HTTP_201_CREATED)
async def create_test(
    payload: TestCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_repo.create_test(
        db,
        title=payload.title,
        description=payload.description,
        time_limit_minutes=payload.time_limit_minutes,
        max_score=payload.max_score,
        published=payload.published,
        material_id=payload.material_id,
        material_ids=payload.material_ids,
        deadline=payload.deadline,
    )
    await delete_pattern("tests:list:*")
    await delete_pattern("tests:detail:*")
    await delete_pattern("tests:content:*")
    await delete_pattern("test:*:summary*")
    await delete_pattern("materials:*")
    return test


@router.patch("/{test_id}", response_model=TestRead, status_code=status.HTTP_200_OK)
async def update_test(
    test_id: int,
    payload: TestUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_repo.update_test(db, test_id, **payload.model_dump(exclude_unset=True))
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    await delete_pattern("tests:list:*")
    await delete_pattern("tests:detail:*")
    await delete_pattern("tests:content:*")
    await delete_pattern(f"test:{test_id}:summary*")
    await delete_pattern("materials:*")
    return test


@router.post("/{test_id}/publish", response_model=TestRead, status_code=status.HTTP_200_OK)
async def publish_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_repo.update_test(db, test_id, published=True)
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    await delete_pattern("tests:list:*")
    await delete_pattern("tests:detail:*")
    await delete_pattern("tests:content:*")
    await delete_pattern(f"test:{test_id}:summary*")
    return test


@router.post("/{test_id}/hide", response_model=TestRead, status_code=status.HTTP_200_OK)
async def hide_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_repo.update_test(db, test_id, published=False)
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    await delete_pattern("tests:list:*")
    await delete_pattern("tests:detail:*")
    await delete_pattern("tests:content:*")
    await delete_pattern(f"test:{test_id}:summary*")
    return test


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    deleted = await test_repo.delete_test(db, test_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    await delete_pattern("tests:list:*")
    await delete_pattern("tests:detail:*")
    await delete_pattern("tests:content:*")
    await delete_pattern(f"test:{test_id}:summary*")
    await delete_pattern("materials:*")
    return {}


@router.get("/{test_id}/summary", response_model=TestSummary, status_code=status.HTTP_200_OK)
async def test_summary(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_teacher = current_user.role in {"teacher", "admin"}
    cache_key = cache_key_test_summary(test_id)
    if not is_teacher:
        cached = await get(cache_key)
        if cached is not None:
            return cached

    test = await test_repo.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.published and not is_teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    summary = await test_repo.get_test_summary(db, test_id)
    if test.published:
        await set(cache_key, summary, ttl=TEST_SUMMARY_TTL)
    return summary


@router.get("/{test_id}/content", response_model=TestContentRead, status_code=status.HTTP_200_OK)
async def get_test_content(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_teacher = current_user.role in {"teacher", "admin"}
    cache_key = cache_key_test_content(test_id)
    if not is_teacher:
        cached = await get(cache_key)
        if cached is not None:
            return cached

    test = await test_repo.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.published and not is_teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    questions = await question_repo.list_questions_for_test(db, test_id=test_id, limit=500, offset=0)
    payload = {
        "test": TestRead.model_validate(test).model_dump(mode="json"),
        "questions": [QuestionRead.model_validate(question).model_dump(mode="json") for question in questions],
    }
    if test.published:
        await set(cache_key, payload, ttl=TEST_CONTENT_TTL)
    return payload


@router.post("/{test_id}/attempts/start", response_model=TestAttemptRead, status_code=status.HTTP_201_CREATED)
async def start_test_attempt(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = await test_repo.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.published and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    existing_attempt = await test_attempt_repo.get_active_attempt(db, current_user.id, test_id)
    if existing_attempt is not None:
        return existing_attempt
    return await test_attempt_repo.create_attempt(db, current_user.id, test_id)


@router.get("/{test_id}/attempts/me", response_model=List[TestAttemptRead], status_code=status.HTTP_200_OK)
async def list_my_test_attempts(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = await test_repo.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.published and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return await test_attempt_repo.list_attempts_for_user(db, current_user.id, test_id=test_id)


@router.post("/attempts/{attempt_id}/complete", response_model=TestAttemptRead, status_code=status.HTTP_200_OK)
async def complete_test_attempt(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await test_attempt_repo.get_attempt(db, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != current_user.id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if attempt.status == "completed":
        return attempt
    completed_attempt = await test_attempt_repo.complete_attempt(db, attempt)
    await analytics_repo.register_completed_attempt(db, completed_attempt.user_id)
    return completed_attempt

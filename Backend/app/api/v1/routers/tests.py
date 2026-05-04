from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import (
    get_manageable_test,
    get_user_level_context,
    get_visible_test,
    is_unlocked_test,
)
from app.api.deps import get_db
from app.cache.redis_cache import (
    NS_MATERIALS,
    NS_QUESTIONS,
    NS_TESTS,
    NS_TEST_CONTENT,
    NS_TEST_SUMMARY,
    TEST_CONTENT_TTL,
    TESTS_CATALOG_TTL,
    TESTS_LIST_TTL,
    TEST_DETAIL_TTL,
    TEST_SUMMARY_TTL,
    bump_cache_namespace,
    cache_key_test_content_for_user,
    cache_key_test_content,
    cache_key_test_detail,
    cache_key_test_list,
    cache_key_tests_catalog_me,
    cache_key_test_summary,
    get_cache_namespace_version,
    get,
    set,
)
from app.core.security import get_current_user, require_roles
from app.models.user import User
from app.schemas.grading import AttemptScoreUpdate
from app.schemas.question import QuestionRead
from app.schemas.test_ import TestCardRead, TestCreate, TestRead, TestUpdate
from app.schemas.analytics import TestSummary
from app.schemas.test_attempt import TestAttemptQuotaRead, TestAttemptRead, TestAttemptStateRead
from app.schemas.test_content import TestContentRead, TestContentWrite
from app.repositories import analytics_repo, test_repo, test_attempt_repo
from app.repositories import question_repo
from app.services import test_service
from app.services.challenge_service import ChallengeEventType, record_event
from app.services.test_runtime import AttemptPolicyError, finalize_attempt_if_expired, resolve_attempt_for_user, utcnow

router = APIRouter()


def _build_attempt_state_payload(
    *,
    test,
    attempt,
    expired_reason: str | None = None,
) -> TestAttemptStateRead:
    reference_time = attempt.completed_at or utcnow()
    elapsed_seconds = max(int((reference_time - attempt.started_at).total_seconds()), 0)

    remaining_seconds: int | None = None
    time_limit_minutes = test.time_limit_minutes
    if time_limit_minutes is not None:
        total_limit_seconds = int(time_limit_minutes) * 60
        remaining_seconds = max(total_limit_seconds - elapsed_seconds, 0)

    inferred_reason = expired_reason
    if inferred_reason is None and time_limit_minutes is not None and remaining_seconds == 0:
        inferred_reason = "time_limit"
    if inferred_reason is None and test.deadline is not None and reference_time >= test.deadline:
        inferred_reason = "deadline"

    return TestAttemptStateRead(
        attempt_id=attempt.id,
        test_id=attempt.test_id,
        status=attempt.status,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        time_limit_minutes=time_limit_minutes,
        elapsed_seconds=elapsed_seconds,
        remaining_seconds=remaining_seconds,
        is_expired=inferred_reason in {"time_limit", "deadline"},
        expired_reason=inferred_reason,
    )


@router.get("/", response_model=List[TestRead], status_code=status.HTTP_200_OK)
async def list_tests(
    published_only: bool = True,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not published_only and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    total_points, level_id = await get_user_level_context(db, current_user)
    if published_only:
        version = await get_cache_namespace_version(NS_TESTS)
        cache_key = cache_key_test_list(
            published_only=published_only,
            limit=limit,
            level_id=level_id,
            version=version,
        )
        cached = await get(cache_key)
        if cached is not None:
            return cached

    author_id = current_user.id if (not published_only and current_user.role == "teacher") else None
    items = await test_repo.list_tests(db, published_only=published_only, limit=limit, author_id=author_id)
    if published_only and current_user.role not in {"teacher", "admin"}:
        items = [
            item
            for item in items
            if await is_unlocked_test(db, current_user, item, total_points=total_points)
        ]
    if published_only:
        payload = [TestRead.model_validate(item).model_dump(mode="json") for item in items]
        await set(cache_key, payload, ttl=TESTS_LIST_TTL)
    return items


@router.get("/catalog/me", response_model=List[TestCardRead], status_code=status.HTTP_200_OK)
async def list_tests_with_my_state(
    published_only: bool = True,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not published_only and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    cache_key = None
    should_cache = current_user.role != "admin"
    if should_cache:
        tests_version = await get_cache_namespace_version(NS_TESTS)
        summary_version = await get_cache_namespace_version(NS_TEST_SUMMARY)
        cache_key = cache_key_tests_catalog_me(
            user_id=current_user.id,
            published_only=published_only,
            limit=limit,
            tests_version=tests_version,
            summary_version=summary_version,
        )
        cached = await get(cache_key)
        if cached is not None:
            return cached

    total_points: float | None = None
    if published_only and current_user.role not in {"teacher", "admin"}:
        total_points, _ = await get_user_level_context(db, current_user)

    author_id = current_user.id if (not published_only and current_user.role == "teacher") else None
    items = await test_repo.list_tests(db, published_only=published_only, limit=limit, author_id=author_id)

    if published_only and current_user.role not in {"teacher", "admin"}:
        items = [
            item
            for item in items
            if await is_unlocked_test(db, current_user, item, total_points=total_points)
        ]

    state_map = await test_repo.get_user_test_state_map(
        db,
        user_id=current_user.id,
        tests=items,
    )

    payload: list[TestCardRead] = []
    for item in items:
        base = TestRead.model_validate(item).model_dump(mode="python")
        state = state_map.get(item.id, {})
        payload.append(
            TestCardRead.model_validate(
                {
                    **base,
                    "total_questions": int(state.get("total_questions", 0)),
                    "user_status": state.get("user_status", "not_started"),
                    "has_active_attempt": bool(state.get("has_active_attempt", False)),
                    "active_attempt_id": state.get("active_attempt_id"),
                    "completed_attempts": int(state.get("completed_attempts", 0)),
                    "remaining_attempts": int(state.get("remaining_attempts", max(int(item.max_attempts or 1), 1))),
                    "user_score": state.get("user_score"),
                    "user_max_score": state.get("user_max_score"),
                    "latest_completed_at": state.get("latest_completed_at"),
                }
            )
        )

    if should_cache and cache_key is not None:
        await set(
            cache_key,
            [item.model_dump(mode="json") for item in payload],
            ttl=TESTS_CATALOG_TTL,
        )
    return payload


@router.get("/{test_id}", response_model=TestRead, status_code=status.HTTP_200_OK)
async def get_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_points: float | None = None
    level_id = 0
    if current_user.role not in {"teacher", "admin"}:
        total_points, level_id = await get_user_level_context(db, current_user)
        version = await get_cache_namespace_version(NS_TESTS)
        cache_key = cache_key_test_detail(test_id, level_id=level_id, version=version)
        cached = await get(cache_key)
        if cached is not None:
            return cached

    t = await get_visible_test(db, test_id, current_user, total_points=total_points)
    if t.published:
        payload = TestRead.model_validate(t).model_dump(mode="json")
        version = await get_cache_namespace_version(NS_TESTS)
        await set(cache_key_test_detail(test_id, level_id=level_id, version=version), payload, ttl=TEST_DETAIL_TTL)
    return t


@router.post("/", response_model=TestRead, status_code=status.HTTP_201_CREATED)
async def create_test(
    payload: TestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_service.create_test(db, payload, current_user)
    await bump_cache_namespace(NS_TESTS, NS_TEST_CONTENT, NS_TEST_SUMMARY, NS_MATERIALS)
    return test


@router.patch("/{test_id}", response_model=TestRead, status_code=status.HTTP_200_OK)
async def update_test(
    test_id: int,
    payload: TestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    test = await test_service.update_test(db, test_id, payload, current_user)
    await bump_cache_namespace(NS_TESTS, NS_TEST_CONTENT, NS_TEST_SUMMARY, NS_MATERIALS)
    return test


@router.post("/{test_id}/publish", response_model=TestRead, status_code=status.HTTP_200_OK)
async def publish_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_test(db, test_id, current_user)
    test = await test_repo.update_test(db, test_id, published=True)
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    await bump_cache_namespace(NS_TESTS, NS_TEST_CONTENT, NS_TEST_SUMMARY)
    return test


@router.post("/{test_id}/hide", response_model=TestRead, status_code=status.HTTP_200_OK)
async def hide_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_test(db, test_id, current_user)
    test = await test_repo.update_test(db, test_id, published=False)
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    await bump_cache_namespace(NS_TESTS, NS_TEST_CONTENT, NS_TEST_SUMMARY)
    return test


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await get_manageable_test(db, test_id, current_user)
    deleted = await test_repo.delete_test(db, test_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    await bump_cache_namespace(NS_TESTS, NS_TEST_CONTENT, NS_TEST_SUMMARY, NS_MATERIALS)
    return {}


@router.get("/{test_id}/summary", response_model=TestSummary, status_code=status.HTTP_200_OK)
async def test_summary(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_teacher = current_user.role in {"teacher", "admin"}
    summary_version = await get_cache_namespace_version(NS_TEST_SUMMARY)
    cache_key = cache_key_test_summary(test_id, version=summary_version)
    test = await test_service.get_test_or_summary_access(db, test_id, current_user)
    if not is_teacher:
        cached = await get(cache_key)
        if cached is not None:
            return cached

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
    total_points: float | None = None
    content_version = await get_cache_namespace_version(NS_TEST_CONTENT)
    cache_key = cache_key_test_content(test_id, level_id=-1, version=content_version)
    if not is_teacher:
        cache_key = cache_key_test_content_for_user(
            test_id=test_id,
            user_id=current_user.id,
            version=content_version,
        )
        cached = await get(cache_key)
        if cached is not None:
            return cached
        total_points, _ = await get_user_level_context(db, current_user)

    test = await get_visible_test(db, test_id, current_user, total_points=total_points)

    questions = await question_repo.list_questions_for_test(db, test_id=test_id, limit=500, offset=0)
    payload = {
        "test": TestRead.model_validate(test).model_dump(mode="json"),
        "questions": [QuestionRead.model_validate(question).model_dump(mode="json") for question in questions],
    }
    if test.published:
        await set(cache_key, payload, ttl=TEST_CONTENT_TTL)
    return payload


@router.put("/{test_id}/content", response_model=TestContentRead, status_code=status.HTTP_200_OK)
async def replace_test_content(
    test_id: int,
    payload: TestContentWrite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    test, questions = await test_service.replace_test_content(
        db,
        test_id=test_id,
        payload=payload,
        current_user=current_user,
    )
    await bump_cache_namespace(NS_QUESTIONS, NS_TEST_CONTENT, NS_TEST_SUMMARY)
    return {
        "test": TestRead.model_validate(test).model_dump(mode="json"),
        "questions": [QuestionRead.model_validate(question).model_dump(mode="json") for question in questions],
    }


@router.post("/{test_id}/attempts/start", response_model=TestAttemptRead, status_code=status.HTTP_201_CREATED)
async def start_test_attempt(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = await get_visible_test(db, test_id, current_user)
    try:
        return await resolve_attempt_for_user(db, test, current_user.id)
    except AttemptPolicyError as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@router.get("/{test_id}/attempts/me", response_model=List[TestAttemptRead], status_code=status.HTTP_200_OK)
async def list_my_test_attempts(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_visible_test(db, test_id, current_user)
    return await test_attempt_repo.list_attempts_for_user(db, current_user.id, test_id=test_id)


@router.get("/{test_id}/attempts/quota", response_model=TestAttemptQuotaRead, status_code=status.HTTP_200_OK)
async def get_my_test_attempt_quota(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = await get_visible_test(db, test_id, current_user)
    max_attempts = max(int(test.max_attempts or 1), 1)
    completed_attempts = await test_attempt_repo.count_completed_attempts_for_user_test(db, current_user.id, test_id)
    active_attempt = await test_attempt_repo.get_active_attempt(db, current_user.id, test_id)
    return TestAttemptQuotaRead(
        test_id=test_id,
        max_attempts=max_attempts,
        completed_attempts=completed_attempts,
        remaining_attempts=max(max_attempts - completed_attempts, 0),
        has_active_attempt=active_attempt is not None,
    )


@router.get("/attempts/{attempt_id}/state", response_model=TestAttemptStateRead, status_code=status.HTTP_200_OK)
async def get_attempt_state(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await test_attempt_repo.get_attempt(db, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != current_user.id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    test = await test_service.get_test_or_summary_access(db, attempt.test_id, current_user)
    if current_user.role == "teacher":
        await get_manageable_test(db, attempt.test_id, current_user)

    attempt, reason = await finalize_attempt_if_expired(db, test, attempt)
    return _build_attempt_state_payload(test=test, attempt=attempt, expired_reason=reason)


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
    test = await test_service.get_test_or_summary_access(db, attempt.test_id, current_user)
    if current_user.role == "teacher":
        await get_manageable_test(db, attempt.test_id, current_user)
    if attempt.status == "completed":
        return attempt
    _, _ = await finalize_attempt_if_expired(db, test, attempt)
    if attempt.status == "completed":
        return attempt
    completed_attempt = await test_attempt_repo.complete_attempt(db, attempt)
    await analytics_repo.register_completed_attempt(db, completed_attempt.user_id, attempt_id=completed_attempt.id)
    await record_event(
        db,
        user_id=completed_attempt.user_id,
        event_type=ChallengeEventType.ATTEMPT_COMPLETED,
        increment=1,
    )
    await record_event(
        db,
        user_id=completed_attempt.user_id,
        event_type=ChallengeEventType.STREAK_DAY,
        increment=1,
    )
    return completed_attempt


@router.patch("/attempts/{attempt_id}/score", response_model=TestAttemptRead, status_code=status.HTTP_200_OK)
async def override_attempt_score(
    attempt_id: int,
    payload: AttemptScoreUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    attempt = await test_attempt_repo.get_attempt(db, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if current_user.role == "teacher":
        await get_manageable_test(db, attempt.test_id, current_user)
    if attempt.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt must be completed before final grading")

    if attempt.max_score is None:
        attempt = await test_attempt_repo.refresh_attempt_scores(db, attempt)
    max_score = float(attempt.max_score or 0.0)
    if payload.score < 0 or payload.score > max_score:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Score must be between 0 and {max_score}",
        )

    return await test_attempt_repo.set_manual_score(db, attempt, payload.score)

import asyncio
from datetime import UTC, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import ensure_teacher_or_admin_can_access_user
from app.api.deps import get_db
from app.cache.redis_cache import (
    LEARNING_DASHBOARD_TTL,
    LEADERBOARD_TTL,
    NS_MATERIALS,
    NS_LEADERBOARD,
    NS_TESTS,
    NS_TEST_SUMMARY,
    cache_key_learning_dashboard,
    cache_key_learning_dashboard_stale,
    cache_key_leaderboard_page,
    get,
    get_cache_namespace_version,
    redis_lock,
    set,
)
from app.core.security import get_current_user, require_roles
from app.schemas.analytics import (
    AchievementDefinitionCreate,
    AchievementDefinitionRead,
    AchievementDefinitionUpdate,
    AnalyticsOverviewRead,
    AnalyticsRead,
    ChallengeClaimRead,
    ChallengeCreate,
    ChallengeRead,
    ChallengeUpdate,
    DailyActiveRead,
    GroupAnalyticsSummaryRead,
    LeaderboardEntry,
    LearningDashboardRead,
    PointsLedgerPageRead,
    QuestionStats,
    RetentionEntryRead,
    RewardDefinitionCreate,
    RewardDefinitionRead,
    RewardDefinitionUpdate,
    ScoreBucketRead,
    SeasonCreate,
    SeasonRead,
    SeasonUpdate,
    TestSummary,
    TestAverageScoreRead,
    TestAverageTimeRead,
    UserAchievementRead,
    UserChallengeProgressRead,
    UserBriefRead,
    UserGamificationProgressRead,
    UserPerformanceRead,
    UserRewardRead,
    UserUnlockRead,
    UnlockRuleCreate,
    UnlockRuleRead,
    UnlockRuleSourceType,
    UnlockRuleUpdate,
)
from app.schemas.level import LevelCreate, LevelRead, LevelUpdate
from app.repositories import (
    achievement_repo,
    analytics_repo,
    challenge_repo,
    group_repo,
    level_repo,
    material_repo,
    reward_repo,
    season_repo,
    test_repo,
)
from app.models.user import User
from app.services import challenge_service, reward_service
from app.services.challenge_service import ChallengeClaimError

router = APIRouter()


def _to_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _assert_group_access(current_user: User, group) -> None:
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if current_user.role == "admin":
        return
    if current_user.role == "teacher" and group.teacher_id == current_user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def _validate_unlock_rule_constraints(*, source_type: str, min_level_required: int | None) -> None:
    if min_level_required is not None and min_level_required < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_level_required must be >= 1")
    if source_type == UnlockRuleSourceType.LEVEL.value and min_level_required is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_level_required is required for source_type=level",
        )


def _validate_level_constraints(*, required_points: int) -> None:
    if required_points < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="required_points must be >= 0")


@router.get("/user/{user_id}", response_model=AnalyticsRead, status_code=status.HTTP_200_OK)
async def get_user_analytics(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return analytics for a given user (total points, tests taken, last active, current level etc).
    """
    await ensure_teacher_or_admin_can_access_user(db, current_user, user_id)
    analytics = await analytics_repo.get_user_analytics(db, user_id)
    if not analytics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analytics not found for user")
    return analytics


@router.get("/user/{user_id}/progress", response_model=UserGamificationProgressRead, status_code=status.HTTP_200_OK)
async def get_user_progress(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await ensure_teacher_or_admin_can_access_user(db, current_user, user_id)
    progress = await analytics_repo.get_gamification_progress(db, user_id)
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return progress


@router.get("/me/learning-dashboard", response_model=LearningDashboardRead, status_code=status.HTTP_200_OK)
async def get_my_learning_dashboard(
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tests_version = await get_cache_namespace_version(NS_TESTS)
    materials_version = await get_cache_namespace_version(NS_MATERIALS)
    summary_version = await get_cache_namespace_version(NS_TEST_SUMMARY)
    cache_key = cache_key_learning_dashboard(
        user_id=current_user.id,
        limit=limit,
        tests_version=tests_version,
        materials_version=materials_version,
        summary_version=summary_version,
    )
    stale_cache_key = cache_key_learning_dashboard_stale(user_id=current_user.id, limit=limit)
    stale_ttl = max(LEARNING_DASHBOARD_TTL * 6, 600)
    async def _build_payload() -> dict:
        progress = await analytics_repo.get_gamification_progress(db, current_user.id)
        if progress is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        total_points = float(progress.get("total_points") or 0.0)
        total_materials = await material_repo.count_visible_materials_for_user(
            db,
            role=current_user.role,
            total_points=total_points,
        )

        tests = await test_repo.list_tests(db, published_only=True, limit=limit)
        if current_user.role not in {"teacher", "admin"}:
            tests = [
                test
                for test in tests
                if test.required_level is None or float(test.required_level.required_points or 0.0) <= total_points
            ]

        state_map = await test_repo.get_user_test_state_map(
            db,
            user_id=current_user.id,
            tests=tests,
        )

        test_results: list[dict] = []
        completed_tests = 0
        tests_with_score = 0
        score_sum = 0.0

        for test in tests:
            state = state_map.get(test.id, {})
            user_status = str(state.get("user_status", "not_started"))
            completed_attempts = int(state.get("completed_attempts", 0))
            remaining_attempts = int(state.get("remaining_attempts", max(int(test.max_attempts or 1), 1)))
            has_active_attempt = bool(state.get("has_active_attempt", False))
            score_value = state.get("user_score")
            max_score = state.get("user_max_score")
            if max_score is None and test.max_score is not None:
                max_score = float(test.max_score)

            score_percent = None
            if score_value is not None and max_score is not None and float(max_score) > 0:
                score_percent = round((float(score_value) / float(max_score)) * 100.0, 2)
                score_sum += float(score_percent)
                tests_with_score += 1

            if user_status == "completed":
                completed_tests += 1

            test_results.append(
                {
                    "test_id": int(test.id),
                    "title": test.title,
                    "deadline": test.deadline,
                    "user_status": user_status,
                    "has_active_attempt": has_active_attempt,
                    "completed_attempts": completed_attempts,
                    "remaining_attempts": remaining_attempts,
                    "score_percent": score_percent,
                    "score_value": float(score_value) if score_value is not None else None,
                    "max_score": float(max_score) if max_score is not None else None,
                    "completed_at": state.get("latest_completed_at"),
                }
            )

        average_score_percent = round(score_sum / tests_with_score, 2) if tests_with_score > 0 else 0.0
        payload = {
            "user_id": int(progress["user_id"]),
            "username": progress["username"],
            "total_points": total_points,
            "streak_days": int(progress.get("streak_days") or 0),
            "total_materials": total_materials,
            "total_tests": len(tests),
            "completed_tests": completed_tests,
            "tests_with_score": tests_with_score,
            "average_score_percent": average_score_percent,
            "current_level": progress.get("current_level"),
            "next_level": progress.get("next_level"),
            "points_to_next_level": float(progress.get("points_to_next_level") or 0.0),
            "progress_percent": float(progress.get("progress_percent") or 0.0),
            "badges": progress.get("badges") or [],
            "test_results": test_results,
        }
        return LearningDashboardRead.model_validate(payload).model_dump(mode="json")

    # Fast path
    cached = await get(cache_key)
    if cached is not None:
        return cached
    stale_cached = await get(stale_cache_key)

    # Anti-stampede path for concurrent misses.
    lock_key = f"lock:{cache_key}"
    try:
        async with redis_lock(lock_key, timeout=15) as locked:
            if not locked:
                # Another request is likely computing fresh data. Return stale fast.
                if stale_cached is not None:
                    return stale_cached
                # Small wait loop to catch just-written fresh cache and avoid duplicate DB-heavy work.
                for _ in range(4):
                    await asyncio.sleep(0.05)
                    warmed = await get(cache_key)
                    if warmed is not None:
                        return warmed
            cached_after_lock = await get(cache_key)
            if cached_after_lock is not None:
                return cached_after_lock
            payload = await _build_payload()
            await set(cache_key, payload, ttl=LEARNING_DASHBOARD_TTL)
            await set(stale_cache_key, payload, ttl=stale_ttl)
            return payload
    except Exception:
        if stale_cached is not None:
            return stale_cached
        payload = await _build_payload()
        await set(cache_key, payload, ttl=LEARNING_DASHBOARD_TTL)
        await set(stale_cache_key, payload, ttl=stale_ttl)
        return payload


@router.get("/me/achievements", response_model=List[UserAchievementRead], status_code=status.HTTP_200_OK)
async def get_my_achievements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await analytics_repo.list_user_achievements(db, current_user.id)


@router.get("/me/points-ledger", response_model=PointsLedgerPageRead, status_code=status.HTTP_200_OK)
async def get_my_points_ledger(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = await analytics_repo.list_points_ledger_for_user(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/me/rewards", response_model=List[UserRewardRead], status_code=status.HTTP_200_OK)
async def get_my_rewards(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await reward_service.list_user_rewards(db, current_user.id)


@router.get("/me/unlocks", response_model=List[UserUnlockRead], status_code=status.HTTP_200_OK)
async def get_my_unlocks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await reward_service.list_user_unlocks(db, current_user.id)


@router.post("/achievement-definitions", response_model=AchievementDefinitionRead, status_code=status.HTTP_201_CREATED)
async def create_achievement_definition(
    payload: AchievementDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    if payload.threshold_value < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="threshold_value must be >= 1")

    existing = await achievement_repo.get_achievement_definition_by_code(db, payload.code)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Achievement definition code already exists",
        )

    try:
        created = await achievement_repo.create_achievement_definition(
            db,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            reward=payload.reward,
            criteria_type=payload.criteria_type.value,
            threshold_value=payload.threshold_value,
            is_active=payload.is_active,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create achievement definition",
        ) from exc
    return created


@router.get("/achievement-definitions", response_model=List[AchievementDefinitionRead], status_code=status.HTTP_200_OK)
async def list_achievement_definitions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return await achievement_repo.list_achievement_definitions(db, limit=limit, offset=offset)


@router.get(
    "/achievement-definitions/{achievement_definition_id}",
    response_model=AchievementDefinitionRead,
    status_code=status.HTTP_200_OK,
)
async def get_achievement_definition(
    achievement_definition_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    definition = await achievement_repo.get_achievement_definition(db, achievement_definition_id)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement definition not found")
    return definition


@router.patch(
    "/achievement-definitions/{achievement_definition_id}",
    response_model=AchievementDefinitionRead,
    status_code=status.HTTP_200_OK,
)
async def update_achievement_definition(
    achievement_definition_id: int,
    payload: AchievementDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    current = await achievement_repo.get_achievement_definition(db, achievement_definition_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement definition not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be provided")

    if "threshold_value" in changes and changes["threshold_value"] < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="threshold_value must be >= 1")

    next_code = changes.get("code", current.code)
    if next_code != current.code:
        existing = await achievement_repo.get_achievement_definition_by_code(db, next_code)
        if existing is not None and existing.id != achievement_definition_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Achievement definition code already exists",
            )

    if "criteria_type" in changes:
        changes["criteria_type"] = changes["criteria_type"].value

    try:
        updated = await achievement_repo.update_achievement_definition(db, achievement_definition_id, **changes)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to update achievement definition",
        ) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement definition not found")
    return updated


@router.delete("/achievement-definitions/{achievement_definition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_achievement_definition(
    achievement_definition_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    deleted = await achievement_repo.delete_achievement_definition(db, achievement_definition_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement definition not found")
    return {}


@router.post("/reward-definitions", response_model=RewardDefinitionRead, status_code=status.HTTP_201_CREATED)
async def create_reward_definition(
    payload: RewardDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    existing = await reward_repo.get_reward_definition_by_code(db, payload.code)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reward definition code already exists")
    try:
        created = await reward_repo.create_reward_definition(
            db,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            reward_type=payload.reward_type,
            payload_json=payload.payload_json,
            is_active=payload.is_active,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create reward definition") from exc
    return created


@router.get("/reward-definitions", response_model=List[RewardDefinitionRead], status_code=status.HTTP_200_OK)
async def list_reward_definitions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return await reward_repo.list_reward_definitions(db, limit=limit, offset=offset)


@router.get("/reward-definitions/{reward_definition_id}", response_model=RewardDefinitionRead, status_code=status.HTTP_200_OK)
async def get_reward_definition(
    reward_definition_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    reward_definition = await reward_repo.get_reward_definition(db, reward_definition_id)
    if reward_definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward definition not found")
    return reward_definition


@router.patch("/reward-definitions/{reward_definition_id}", response_model=RewardDefinitionRead, status_code=status.HTTP_200_OK)
async def update_reward_definition(
    reward_definition_id: int,
    payload: RewardDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    current = await reward_repo.get_reward_definition(db, reward_definition_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward definition not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be provided")

    next_code = changes.get("code", current.code)
    if next_code != current.code:
        existing = await reward_repo.get_reward_definition_by_code(db, next_code)
        if existing is not None and existing.id != reward_definition_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reward definition code already exists")

    try:
        updated = await reward_repo.update_reward_definition(db, reward_definition_id, **changes)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to update reward definition") from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward definition not found")
    return updated


@router.delete("/reward-definitions/{reward_definition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reward_definition(
    reward_definition_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    deleted = await reward_repo.delete_reward_definition(db, reward_definition_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward definition not found")
    return {}


@router.post("/unlock-rules", response_model=UnlockRuleRead, status_code=status.HTTP_201_CREATED)
async def create_unlock_rule(
    payload: UnlockRuleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    source_type = payload.source_type.value
    _validate_unlock_rule_constraints(source_type=source_type, min_level_required=payload.min_level_required)

    reward_definition = await reward_repo.get_reward_definition(db, payload.reward_definition_id)
    if reward_definition is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reward_definition_id is invalid")

    try:
        created = await reward_repo.create_unlock_rule(
            db,
            reward_definition_id=payload.reward_definition_id,
            source_type=source_type,
            source_code=payload.source_code,
            min_level_required=payload.min_level_required,
            is_active=payload.is_active,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unlock rule already exists") from exc
    return created


@router.get("/unlock-rules", response_model=List[UnlockRuleRead], status_code=status.HTTP_200_OK)
async def list_unlock_rules(
    reward_definition_id: int | None = Query(default=None, ge=1),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return await reward_repo.list_unlock_rules(
        db,
        reward_definition_id=reward_definition_id,
        limit=limit,
        offset=offset,
    )


@router.get("/unlock-rules/{unlock_rule_id}", response_model=UnlockRuleRead, status_code=status.HTTP_200_OK)
async def get_unlock_rule(
    unlock_rule_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    unlock_rule = await reward_repo.get_unlock_rule(db, unlock_rule_id)
    if unlock_rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unlock rule not found")
    return unlock_rule


@router.patch("/unlock-rules/{unlock_rule_id}", response_model=UnlockRuleRead, status_code=status.HTTP_200_OK)
async def update_unlock_rule(
    unlock_rule_id: int,
    payload: UnlockRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    current = await reward_repo.get_unlock_rule(db, unlock_rule_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unlock rule not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be provided")

    source_type = changes.get("source_type", current.source_type)
    if isinstance(source_type, UnlockRuleSourceType):
        source_type = source_type.value
    min_level_required = changes.get("min_level_required", current.min_level_required)
    _validate_unlock_rule_constraints(source_type=source_type, min_level_required=min_level_required)

    reward_definition_id = changes.get("reward_definition_id", current.reward_definition_id)
    reward_definition = await reward_repo.get_reward_definition(db, reward_definition_id)
    if reward_definition is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reward_definition_id is invalid")

    if "source_type" in changes and isinstance(changes["source_type"], UnlockRuleSourceType):
        changes["source_type"] = changes["source_type"].value

    try:
        updated = await reward_repo.update_unlock_rule(db, unlock_rule_id, **changes)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unlock rule already exists") from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unlock rule not found")
    return updated


@router.delete("/unlock-rules/{unlock_rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unlock_rule(
    unlock_rule_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    deleted = await reward_repo.delete_unlock_rule(db, unlock_rule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unlock rule not found")
    return {}


@router.post("/challenges", response_model=ChallengeRead, status_code=status.HTTP_201_CREATED)
async def create_challenge(
    payload: ChallengeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    try:
        challenge = await challenge_service.create_challenge(
            db,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            period_type=payload.period_type,
            event_type=payload.event_type,
            target_value=payload.target_value,
            reward_points=payload.reward_points,
            is_active=payload.is_active,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return challenge


@router.get("/challenges", response_model=List[ChallengeRead], status_code=status.HTTP_200_OK)
async def list_challenges(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return await challenge_repo.list_challenges(db, limit=limit, offset=offset)


@router.get("/challenges/{challenge_id}", response_model=ChallengeRead, status_code=status.HTTP_200_OK)
async def get_challenge(
    challenge_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    challenge = await challenge_repo.get_challenge(db, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    return challenge


@router.patch("/challenges/{challenge_id}", response_model=ChallengeRead, status_code=status.HTTP_200_OK)
async def update_challenge(
    challenge_id: int,
    payload: ChallengeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be provided")
    try:
        updated = await challenge_service.update_challenge(
            db,
            challenge_id=challenge_id,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            period_type=payload.period_type,
            event_type=payload.event_type,
            target_value=payload.target_value,
            reward_points=payload.reward_points,
            is_active=payload.is_active,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    return updated


@router.delete("/challenges/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_challenge(
    challenge_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    deleted = await challenge_repo.delete_challenge(db, challenge_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    return {}


@router.get("/me/challenges/active", response_model=List[UserChallengeProgressRead], status_code=status.HTTP_200_OK)
async def list_my_active_challenges(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await challenge_service.list_active_challenges_with_progress(
        db,
        user_id=current_user.id,
    )


@router.post("/me/challenges/{challenge_id}/claim", response_model=ChallengeClaimRead, status_code=status.HTTP_200_OK)
async def claim_my_challenge(
    challenge_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await challenge_service.claim_challenge(
            db,
            user_id=current_user.id,
            challenge_id=challenge_id,
        )
    except ChallengeClaimError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.lower().endswith("not found") else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/user/{user_id}/achievements", response_model=List[UserAchievementRead], status_code=status.HTTP_200_OK)
async def get_user_achievements(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await ensure_teacher_or_admin_can_access_user(db, current_user, user_id)
    return await analytics_repo.list_user_achievements(db, user_id)


@router.get("/user/{user_id}/points-ledger", response_model=PointsLedgerPageRead, status_code=status.HTTP_200_OK)
async def get_user_points_ledger(
    user_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await ensure_teacher_or_admin_can_access_user(db, current_user, user_id)
    items = await analytics_repo.list_points_ledger_for_user(
        db,
        user_id,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/leaderboard", response_model=List[LeaderboardEntry], status_code=status.HTTP_200_OK)
async def leaderboard(
    scope: str = Query("global", pattern="^(global|group)$"),
    period: str = Query("all_time", pattern="^(all_time|week|season)$"),
    group_id: int | None = Query(default=None, ge=1),
    season_id: int | None = Query(default=None, ge=1),
    limit: int = Query(50, ge=1, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Leaderboard by total_points with optional scope and period."""
    if scope == "group":
        if group_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="group_id is required for scope=group")
        group = await group_repo.get_group(db, group_id)
        _assert_group_access(current_user, group)
    if period == "season" and season_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="season_id is required for period=season")

    version = await get_cache_namespace_version(NS_LEADERBOARD)
    cache_key = cache_key_leaderboard_page(
        limit=limit,
        offset=offset,
        version=version,
        scope=scope,
        period=period,
        group_id=group_id,
        season_id=season_id,
    )
    cached = await get(cache_key)
    if cached is not None:
        return cached

    try:
        lb = await analytics_repo.get_leaderboard_scoped(
            db,
            limit=limit,
            offset=offset,
            scope=scope,
            period=period,
            group_id=group_id,
            season_id=season_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    await set(cache_key, lb, ttl=LEADERBOARD_TTL)
    return lb


@router.post("/seasons", response_model=SeasonRead, status_code=status.HTTP_201_CREATED)
async def create_season(
    payload: SeasonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    starts_at = _to_naive_utc(payload.starts_at)
    ends_at = _to_naive_utc(payload.ends_at)
    if starts_at is None or ends_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="starts_at and ends_at are required")
    if ends_at < starts_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ends_at must be >= starts_at")
    existing = await season_repo.get_season_by_code(db, payload.code)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Season code already exists")
    season = await season_repo.create_season(
        db,
        code=payload.code,
        title=payload.title,
        starts_at=starts_at,
        ends_at=ends_at,
        is_active=payload.is_active,
        created_by=current_user.id,
    )
    return season


@router.get("/seasons", response_model=List[SeasonRead], status_code=status.HTTP_200_OK)
async def list_seasons(
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await season_repo.list_seasons(db, only_active=active_only)


@router.get("/seasons/{season_id}", response_model=SeasonRead, status_code=status.HTTP_200_OK)
async def get_season(
    season_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    season = await season_repo.get_season(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return season


@router.patch("/seasons/{season_id}", response_model=SeasonRead, status_code=status.HTTP_200_OK)
async def update_season(
    season_id: int,
    payload: SeasonUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    season = await season_repo.get_season(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be provided")

    next_code = changes.get("code", season.code)
    if next_code != season.code:
        existing = await season_repo.get_season_by_code(db, next_code)
        if existing is not None and existing.id != season_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Season code already exists")

    if "starts_at" in changes:
        changes["starts_at"] = _to_naive_utc(changes["starts_at"])
    if "ends_at" in changes:
        changes["ends_at"] = _to_naive_utc(changes["ends_at"])

    next_starts_at = _to_naive_utc(changes.get("starts_at", season.starts_at))
    next_ends_at = _to_naive_utc(changes.get("ends_at", season.ends_at))
    if next_starts_at is None or next_ends_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="starts_at and ends_at are required")
    if next_ends_at < next_starts_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ends_at must be >= starts_at")

    updated = await season_repo.update_season(db, season_id, **changes)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return updated


@router.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_season(
    season_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    deleted = await season_repo.delete_season(db, season_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return {}


@router.get("/overview", response_model=AnalyticsOverviewRead, status_code=status.HTTP_200_OK)
async def analytics_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    return await analytics_repo.analytics_overview(db)


@router.post("/levels", response_model=LevelRead, status_code=status.HTTP_201_CREATED)
async def create_level(
    payload: LevelCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    _validate_level_constraints(required_points=payload.required_points)

    existing_by_name = await level_repo.get_level_by_name(db, payload.name)
    if existing_by_name is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Level name already exists")

    existing_by_required_points = await level_repo.get_level_by_required_points(db, payload.required_points)
    if existing_by_required_points is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="required_points must be unique")

    try:
        level = await level_repo.create_level(
            db,
            name=payload.name,
            required_points=payload.required_points,
            description=payload.description,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create level") from exc
    return level


@router.get("/levels", response_model=List[LevelRead], status_code=status.HTTP_200_OK)
async def list_levels(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Return configured levels (id, name, required_points, description).
    """
    lvls = await level_repo.list_levels(db)
    return lvls


@router.get("/levels/{level_id}", response_model=LevelRead, status_code=status.HTTP_200_OK)
async def get_level(
    level_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    level = await level_repo.get_level_by_id(db, level_id)
    if level is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found")
    return level


@router.patch("/levels/{level_id}", response_model=LevelRead, status_code=status.HTTP_200_OK)
async def update_level(
    level_id: int,
    payload: LevelUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    level = await level_repo.get_level_by_id(db, level_id)
    if level is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be provided")

    next_name = changes.get("name", level.name)
    if next_name != level.name:
        existing_by_name = await level_repo.get_level_by_name(db, next_name)
        if existing_by_name is not None and existing_by_name.id != level_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Level name already exists")

    next_required_points = changes.get("required_points", level.required_points)
    _validate_level_constraints(required_points=next_required_points)
    if next_required_points != level.required_points:
        existing_by_required_points = await level_repo.get_level_by_required_points(db, next_required_points)
        if existing_by_required_points is not None and existing_by_required_points.id != level_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="required_points must be unique")

    try:
        updated = await level_repo.update_level(db, level_id, **changes)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to update level") from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found")
    return updated


@router.delete("/levels/{level_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_level(
    level_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    try:
        deleted = await level_repo.delete_level(db, level_id)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Level is referenced by existing tests/materials",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found")
    return {}


@router.get("/level/{level_id}/below", response_model=List[UserBriefRead], status_code=status.HTTP_200_OK)
async def users_below_level(
    level_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """
    List users whose total_points are below the required points for the level.
    """
    users = await analytics_repo.users_below_level(db, level_id)
    return [{"user_id": u.id, "username": u.username} for u in users]


@router.get("/level/{level_id}/reached", response_model=List[UserBriefRead], status_code=status.HTTP_200_OK)
async def users_reached_level(
    level_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """
    List users who currently have this level assigned (by current_level_id).
    """
    users = await analytics_repo.users_reached_level(db, level_id)
    return [{"user_id": u.id, "username": u.username} for u in users]


@router.get("/question/{question_id}/stats", response_model=QuestionStats, status_code=status.HTTP_200_OK)
async def question_stats(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """
    Returns statistics for a question: attempts, avg_score, correct_count, correct_rate, distinct_users.
    """
    stats = await analytics_repo.question_statistics(db, question_id)
    return stats


@router.get("/test/{test_id}/avg_score", response_model=TestAverageScoreRead, status_code=status.HTTP_200_OK)
async def avg_score_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """
    Average score for a given test across attempts.
    """
    avg = await analytics_repo.average_score_per_test(db, test_id)
    return {"test_id": test_id, "avg_score": avg}


@router.get("/test/{test_id}/avg_time", response_model=TestAverageTimeRead, status_code=status.HTTP_200_OK)
async def avg_time_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    avg = await analytics_repo.average_time_per_test(db, test_id)
    return {"test_id": test_id, "avg_time_seconds": avg}


@router.get("/test/{test_id}/completed-summary", response_model=TestSummary, status_code=status.HTTP_200_OK)
async def completed_summary_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    summary = await analytics_repo.completed_attempt_summary_for_test(db, test_id)
    base = await test_repo.get_test_summary(db, test_id)
    return {
        "test_id": test_id,
        "total_questions": base["total_questions"],
        "total_attempts": base["total_attempts"],
        "completed_attempts": summary["completed_attempts"],
        "avg_score": summary["avg_score"],
        "avg_time_seconds": summary["avg_time_seconds"],
    }


@router.get("/test/{test_id}/score-distribution", response_model=List[ScoreBucketRead], status_code=status.HTTP_200_OK)
async def score_distribution_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    return await analytics_repo.test_score_distribution(db, test_id)


@router.get("/user/{user_id}/performance", response_model=UserPerformanceRead, status_code=status.HTTP_200_OK)
async def user_performance(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await ensure_teacher_or_admin_can_access_user(db, current_user, user_id)
    performance = await analytics_repo.user_performance(db, user_id)
    if performance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return performance


@router.get("/group/{group_id}/summary", response_model=GroupAnalyticsSummaryRead, status_code=status.HTTP_200_OK)
async def group_summary(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = await group_repo.get_group(db, group_id)
    _assert_group_access(current_user, group)
    return await analytics_repo.group_summary(db, group_id)


@router.get("/group/{group_id}/members", response_model=List[UserPerformanceRead], status_code=status.HTTP_200_OK)
async def group_members_performance(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    group = await group_repo.get_group(db, group_id)
    _assert_group_access(current_user, group)
    return await analytics_repo.group_member_performance(db, group_id)


@router.get("/dau", response_model=List[DailyActiveRead], status_code=status.HTTP_200_OK)
async def daily_active(
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """
    Daily active users over the last `days` days.
    """
    res = await analytics_repo.daily_active_users(db, days=days)
    return res


@router.get("/retention", response_model=List[RetentionEntryRead], status_code=status.HTTP_200_OK)
async def retention_cohort(
    start_date: str,
    period_days: int = Query(7, ge=1),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """
    Simple retention/cohort report.
    Query params:
      - start_date: 'YYYY-MM-DD'
      - period_days: window length
    """
    res = await analytics_repo.retention_cohort(db, start_date=start_date, period_days=period_days)
    return res

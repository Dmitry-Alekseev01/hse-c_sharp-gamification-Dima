from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.cache.redis_cache import (
    LEADERBOARD_TTL,
    NS_LEADERBOARD,
    cache_key_leaderboard_page,
    get,
    get_cache_namespace_version,
    set,
)
from app.core.security import get_current_user, require_roles
from app.schemas.analytics import (
    AnalyticsOverviewRead,
    AnalyticsRead,
    ChallengeClaimRead,
    ChallengeCreate,
    ChallengeRead,
    DailyActiveRead,
    GroupAnalyticsSummaryRead,
    LeaderboardEntry,
    PointsLedgerPageRead,
    QuestionStats,
    RetentionEntryRead,
    ScoreBucketRead,
    SeasonCreate,
    SeasonRead,
    TestSummary,
    TestAverageScoreRead,
    TestAverageTimeRead,
    UserAchievementRead,
    UserChallengeProgressRead,
    UserBriefRead,
    UserGamificationProgressRead,
    UserRewardRead,
    UserUnlockRead,
    UserPerformanceRead,
)
from app.schemas.level import LevelRead
from app.repositories import analytics_repo, group_repo, level_repo, season_repo, test_repo, user_repo
from app.models.user import User
from app.services import challenge_service, reward_service
from app.services.challenge_service import ChallengeClaimError

router = APIRouter()


def _assert_group_access(current_user: User, group) -> None:
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if current_user.role == "admin":
        return
    if current_user.role == "teacher" and group.teacher_id == current_user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


async def _assert_student_access(
    db: AsyncSession,
    current_user: User,
    user_id: int,
) -> None:
    user = await user_repo.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role == "admin":
        return
    if current_user.role == "teacher":
        if current_user.id == user_id:
            return
        if await group_repo.teacher_manages_user(db, current_user.id, user_id):
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.get("/user/{user_id}", response_model=AnalyticsRead, status_code=status.HTTP_200_OK)
async def get_user_analytics(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return analytics for a given user (total points, tests taken, last active, current level etc).
    """
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
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
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    progress = await analytics_repo.get_gamification_progress(db, user_id)
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return progress


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
    await _assert_student_access(db, current_user, user_id)
    return await analytics_repo.list_user_achievements(db, user_id)


@router.get("/user/{user_id}/points-ledger", response_model=PointsLedgerPageRead, status_code=status.HTTP_200_OK)
async def get_user_points_ledger(
    user_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    await _assert_student_access(db, current_user, user_id)
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
    if payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ends_at must be >= starts_at")
    existing = await season_repo.get_season_by_code(db, payload.code)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Season code already exists")
    season = await season_repo.create_season(
        db,
        code=payload.code,
        title=payload.title,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
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


@router.get("/overview", response_model=AnalyticsOverviewRead, status_code=status.HTTP_200_OK)
async def analytics_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    return await analytics_repo.analytics_overview(db)


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
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
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

from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_user, require_roles
from app.schemas.analytics import AnalyticsRead, TestSummary
from app.schemas.level import LevelRead
from app.repositories import analytics_repo, level_repo, test_repo
from app.models.user import User

router = APIRouter()


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
        # Could be that row not created yet — return 404 or an empty/zero object depending on your policy.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analytics not found for user")
    return analytics


@router.get("/leaderboard", status_code=status.HTTP_200_OK)
async def leaderboard(
    limit: int = Query(50, ge=1, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Leaderboard by total_points (descending). Returns list of {id, username, total_points}
    """
    lb = await analytics_repo.get_leaderboard(db, limit=limit, offset=offset)
    return lb


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


@router.get("/level/{level_id}/below", status_code=status.HTTP_200_OK)
async def users_below_level(
    level_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """
    List users whose total_points are below the required points for the level.
    """
    users = await analytics_repo.users_below_level(db, level_id)
    # return simple list of user dicts
    return [{"id": getattr(u, "id", None), "username": getattr(u, "username", None)} for u in users]


@router.get("/level/{level_id}/reached", status_code=status.HTTP_200_OK)
async def users_reached_level(
    level_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """
    List users who currently have this level assigned (by current_level_id).
    """
    users = await analytics_repo.users_reached_level(db, level_id)
    return [{"id": getattr(u, "id", None), "username": getattr(u, "username", None)} for u in users]


@router.get("/question/{question_id}/stats", status_code=status.HTTP_200_OK)
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


@router.get("/test/{test_id}/avg_score", status_code=status.HTTP_200_OK)
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


@router.get("/test/{test_id}/avg_time", status_code=status.HTTP_200_OK)
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


@router.get("/dau", status_code=status.HTTP_200_OK)
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


@router.get("/retention", status_code=status.HTTP_200_OK)
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

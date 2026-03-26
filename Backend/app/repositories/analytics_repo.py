from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import Analytics
from app.models.user import User
from app.models.answer import Answer
from app.models.level import Level
from app.models.test_attempt import TestAttempt


async def get_analytics_for_user(session: AsyncSession, user_id: int) -> Optional[Analytics]:
    q = select(Analytics).where(Analytics.user_id == user_id)
    res = await session.execute(q)
    return res.scalars().first()


async def create_or_update_analytics(
    session: AsyncSession,
    user_id: int,
    points_delta: float = 0.0,
    mark_active: bool = False
) -> Analytics:
    """
    Универсальный upsert без ON CONFLICT.
    """
    # Пытаемся найти существующую запись
    stmt = select(Analytics).where(Analytics.user_id == user_id)
    result = await session.execute(stmt)
    analytics = result.scalar_one_or_none()

    if analytics is None:
        analytics = Analytics(
            user_id=user_id,
            total_points=points_delta,
            tests_taken=1 if points_delta > 0 else 0,
            last_active=func.now() if mark_active else None
        )
        session.add(analytics)
    else:
        analytics.total_points += points_delta
        if points_delta > 0:
            analytics.tests_taken += 1
        if mark_active:
            analytics.last_active = func.now()

    # Flush, но не commit – вызывающий код решит, когда фиксировать
    await session.flush()
    return analytics


async def get_user_analytics(session: AsyncSession, user_id: int) -> Optional[Analytics]:
    return await get_analytics_for_user(session, user_id)


async def apply_points_delta(session: AsyncSession, user_id: int, points_delta: float) -> Analytics:
    analytics = await get_analytics_for_user(session, user_id)
    if analytics is None:
        analytics = Analytics(user_id=user_id, total_points=0.0, tests_taken=0)
        session.add(analytics)
        await session.flush()

    analytics.total_points = float(analytics.total_points or 0.0) + float(points_delta)
    await session.flush()
    return analytics


async def get_leaderboard(session: AsyncSession, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Leaderboard by total_points (descending).
    Returns list of dicts: {'id', 'username', 'total_points'}
    """
    q = (
        select(User.id.label("id"), User.username.label("username"), Analytics.total_points)
        .join(Analytics, Analytics.user_id == User.id)
        .order_by(desc(Analytics.total_points))
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(q)
    return [dict(row._mapping) for row in res.all()]


async def users_below_level(session: AsyncSession, level_id: int):
    lvl = await session.get(Level, level_id)
    if not lvl:
        return []
    req = lvl.required_points
    q = select(User).join(Analytics, Analytics.user_id == User.id).where(Analytics.total_points < req)
    res = await session.execute(q)
    return res.scalars().all()


async def users_reached_level(session: AsyncSession, level_id: int):
    q = select(User).join(Analytics, Analytics.user_id == User.id).where(Analytics.current_level_id == level_id)
    res = await session.execute(q)
    return res.scalars().all()


async def question_statistics(session: AsyncSession, question_id: int) -> Dict[str, Any]:
    """
    Returns attempts, avg_score, correct_count (MCQ), correct_rate, distinct_users.
    Assumes MCQ payload convention: answer_payload = str(choice_id)
    """
    attempts = await session.scalar(select(func.count(Answer.id)).where(Answer.question_id == question_id))
    avg_score = await session.scalar(select(func.avg(Answer.score)).where(Answer.question_id == question_id))
    distinct_users = await session.scalar(select(func.count(func.distinct(Answer.user_id))).where(Answer.question_id == question_id))

    # correct_count: join answers -> choices where choices.is_correct = true and choices.id::text = answer_payload
    correct_sql = text(
        """
        SELECT COUNT(a.id) AS correct_count
        FROM answers a
        JOIN choices c ON c.id::text = a.answer_payload
        WHERE a.question_id = :qid AND c.is_correct = true
        """
    )
    res = await session.execute(correct_sql, {"qid": question_id})
    correct_count = int(res.scalar_one() or 0)

    correct_rate = (correct_count / attempts) if attempts and attempts > 0 else None

    return {
        "question_id": question_id,
        "attempts": int(attempts or 0),
        "avg_score": float(avg_score) if avg_score is not None else None,
        "correct_count": correct_count,
        "correct_rate": float(correct_rate) if correct_rate is not None else None,
        "distinct_users": int(distinct_users or 0),
    }


async def average_score_per_test(session: AsyncSession, test_id: int) -> Optional[float]:
    avg_ = await session.scalar(
        select(func.avg(TestAttempt.score)).where(
            TestAttempt.test_id == test_id,
            TestAttempt.status == "completed",
        )
    )
    if avg_ is None:
        avg_ = await session.scalar(select(func.avg(Answer.score)).where(Answer.test_id == test_id))
    return float(avg_) if avg_ is not None else None


async def average_time_per_test(session: AsyncSession, test_id: int) -> Optional[float]:
    avg_ = await session.scalar(
        select(func.avg(TestAttempt.time_spent_seconds)).where(
            TestAttempt.test_id == test_id,
            TestAttempt.status == "completed",
        )
    )
    return float(avg_) if avg_ is not None else None


async def completed_attempt_summary_for_test(session: AsyncSession, test_id: int) -> Dict[str, Any]:
    completed_attempts = await session.scalar(
        select(func.count(TestAttempt.id)).where(
            TestAttempt.test_id == test_id,
            TestAttempt.status == "completed",
        )
    )
    avg_score = await average_score_per_test(session, test_id)
    avg_time = await average_time_per_test(session, test_id)
    return {
        "test_id": test_id,
        "completed_attempts": int(completed_attempts or 0),
        "avg_score": avg_score,
        "avg_time_seconds": avg_time,
    }


async def daily_active_users(session: AsyncSession, days: int = 7):
    """
    DAU over last N days: returns list of {day, dau}
    """
    raw = text(
        """
        SELECT date_trunc('day', created_at) AS day, count(DISTINCT user_id) AS dau
        FROM answers
        WHERE created_at >= now() - (:days || ' days')::interval
        GROUP BY day
        ORDER BY day DESC
        """
    )
    res = await session.execute(raw, {"days": days})
    return [{"day": row["day"], "dau": row["dau"]} for row in res.fetchall()]


async def retention_cohort(session: AsyncSession, start_date: str, period_days: int = 7):
    """
    Skeleton cohort implementation (returns simple aggregation). Can be improved to return windows.
    """
    sql = text(
        """
        WITH cohort AS (
          SELECT DISTINCT user_id
          FROM answers
          WHERE created_at >= :start_date::date
            AND created_at < (:start_date::date + (:period_days || ' days')::interval)
        ), activity AS (
          SELECT user_id, date_trunc('day', created_at) as day
          FROM answers
          WHERE created_at >= :start_date::date
        )
        SELECT c.user_id,
          array_agg(DISTINCT a.day) as active_days
        FROM cohort c
        LEFT JOIN activity a ON a.user_id = c.user_id
        GROUP BY c.user_id
        """
    )
    res = await session.execute(sql, {"start_date": start_date, "period_days": period_days})
    rows = res.fetchall()
    return [{"user_id": r["user_id"], "active_days": r["active_days"]} for r in rows]

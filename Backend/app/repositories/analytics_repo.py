from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import Analytics
from app.models.answer import Answer
from app.models.group import GroupMembership
from app.models.level import Level
from app.models.material import Material
from app.models.question import Question
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.models.user import User
from app.repositories import level_repo


async def get_analytics_for_user(session: AsyncSession, user_id: int) -> Optional[Analytics]:
    q = select(Analytics).where(Analytics.user_id == user_id)
    res = await session.execute(q)
    return res.scalars().first()


def _recalculate_streak(last_active: datetime | None, current_streak: int, now: datetime) -> int:
    if last_active is None:
        return 1
    last_date = last_active.date()
    current_date = now.date()
    if last_date == current_date:
        return max(int(current_streak or 0), 1)
    if last_date == current_date - timedelta(days=1):
        return max(int(current_streak or 0), 0) + 1
    return 1


async def _sync_level_and_activity(session: AsyncSession, analytics: Analytics, *, mark_active: bool) -> None:
    now = datetime.utcnow()
    if mark_active:
        analytics.streak_days = _recalculate_streak(analytics.last_active, int(analytics.streak_days or 0), now)
        analytics.last_active = now
    current_level = await level_repo.get_current_level_for_points(session, float(analytics.total_points or 0.0))
    analytics.current_level_id = current_level.id if current_level is not None else None


async def create_or_update_analytics(
    session: AsyncSession,
    user_id: int,
    points_delta: float = 0.0,
    mark_active: bool = False,
    tests_delta: int = 0,
) -> Analytics:
    stmt = select(Analytics).where(Analytics.user_id == user_id)
    result = await session.execute(stmt)
    analytics = result.scalar_one_or_none()

    if analytics is None:
        analytics = Analytics(
            user_id=user_id,
            total_points=float(points_delta),
            tests_taken=max(int(tests_delta), 0),
            last_active=None,
            streak_days=0,
        )
        session.add(analytics)
    else:
        analytics.total_points = float(analytics.total_points or 0.0) + float(points_delta)
        if tests_delta != 0:
            analytics.tests_taken = max(int(analytics.tests_taken or 0) + int(tests_delta), 0)

    await _sync_level_and_activity(session, analytics, mark_active=mark_active)
    await session.flush()
    return analytics


async def get_user_analytics(session: AsyncSession, user_id: int) -> Optional[Analytics]:
    return await get_analytics_for_user(session, user_id)


async def apply_points_delta(session: AsyncSession, user_id: int, points_delta: float) -> Analytics:
    analytics = await get_analytics_for_user(session, user_id)
    if analytics is None:
        analytics = Analytics(user_id=user_id, total_points=0.0, tests_taken=0, streak_days=0)
        session.add(analytics)
        await session.flush()

    analytics.total_points = float(analytics.total_points or 0.0) + float(points_delta)
    await _sync_level_and_activity(session, analytics, mark_active=False)
    await session.flush()
    return analytics


async def register_completed_attempt(session: AsyncSession, user_id: int) -> Analytics:
    return await create_or_update_analytics(
        session,
        user_id=user_id,
        points_delta=0.0,
        mark_active=True,
        tests_delta=1,
    )


async def get_gamification_progress(session: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    analytics = await get_user_analytics(session, user_id)
    user = await session.get(User, user_id)
    if user is None:
        return None

    total_points = float(analytics.total_points) if analytics is not None and analytics.total_points is not None else 0.0
    streak_days = int(analytics.streak_days) if analytics is not None and analytics.streak_days is not None else 0
    current_level = await level_repo.get_current_level_for_points(session, total_points)
    next_level = await level_repo.get_next_level_for_points(session, total_points)

    current_required = float(current_level.required_points) if current_level is not None else 0.0
    next_required = float(next_level.required_points) if next_level is not None else None
    if next_required is None:
        progress_percent = 100.0
        points_to_next_level = 0.0
    else:
        span = max(next_required - current_required, 1.0)
        progress_percent = max(0.0, min(100.0, ((total_points - current_required) / span) * 100.0))
        points_to_next_level = max(next_required - total_points, 0.0)

    return {
        "user_id": user.id,
        "username": user.username,
        "total_points": total_points,
        "streak_days": streak_days,
        "current_level": {
            "id": current_level.id,
            "name": current_level.name,
            "required_points": current_level.required_points,
            "description": current_level.description,
        } if current_level is not None else None,
        "next_level": {
            "id": next_level.id,
            "name": next_level.name,
            "required_points": next_level.required_points,
            "description": next_level.description,
        } if next_level is not None else None,
        "points_to_next_level": points_to_next_level,
        "progress_percent": progress_percent,
    }


async def get_leaderboard(session: AsyncSession, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
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
    q = select(User).join(Analytics, Analytics.user_id == User.id).where(Analytics.total_points < lvl.required_points)
    res = await session.execute(q)
    return res.scalars().all()


async def users_reached_level(session: AsyncSession, level_id: int):
    q = select(User).join(Analytics, Analytics.user_id == User.id).where(Analytics.current_level_id == level_id)
    res = await session.execute(q)
    return res.scalars().all()


async def question_statistics(session: AsyncSession, question_id: int) -> Dict[str, Any]:
    attempts = await session.scalar(select(func.count(Answer.id)).where(Answer.question_id == question_id))
    avg_score = await session.scalar(select(func.avg(Answer.score)).where(Answer.question_id == question_id))
    distinct_users = await session.scalar(select(func.count(func.distinct(Answer.user_id))).where(Answer.question_id == question_id))

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


async def analytics_overview(session: AsyncSession) -> Dict[str, int]:
    total_users = int(await session.scalar(select(func.count(User.id))) or 0)
    total_materials = int(await session.scalar(select(func.count(Material.id))) or 0)
    total_tests = int(await session.scalar(select(func.count(Test.id))) or 0)
    published_tests = int(await session.scalar(select(func.count(Test.id)).where(Test.published.is_(True))) or 0)
    total_questions = int(await session.scalar(select(func.count(Question.id))) or 0)
    total_answers = int(await session.scalar(select(func.count(Answer.id))) or 0)
    completed_attempts = int(await session.scalar(select(func.count(TestAttempt.id)).where(TestAttempt.status == "completed")) or 0)
    pending_open_answers = int(
        await session.scalar(
            select(func.count(Answer.id))
            .join(Question, Answer.question_id == Question.id)
            .where(Question.is_open_answer.is_(True), Answer.score.is_(None))
        ) or 0
    )
    active_users_7d = int(
        await session.scalar(
            select(func.count(func.distinct(Answer.user_id))).where(
                Answer.created_at >= func.now() - text("interval '7 days'")
            )
        ) or 0
    )
    return {
        "total_users": total_users,
        "total_materials": total_materials,
        "total_tests": total_tests,
        "published_tests": published_tests,
        "total_questions": total_questions,
        "total_answers": total_answers,
        "completed_attempts": completed_attempts,
        "pending_open_answers": pending_open_answers,
        "active_users_7d": active_users_7d,
    }


async def user_performance(session: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    user = await session.get(User, user_id)
    if user is None:
        return None

    analytics = await get_user_analytics(session, user_id)
    completed_attempts = int(
        await session.scalar(
            select(func.count(TestAttempt.id)).where(
                TestAttempt.user_id == user_id,
                TestAttempt.status == "completed",
            )
        ) or 0
    )
    avg_score = await session.scalar(
        select(func.avg(TestAttempt.score)).where(
            TestAttempt.user_id == user_id,
            TestAttempt.status == "completed",
        )
    )
    avg_time = await session.scalar(
        select(func.avg(TestAttempt.time_spent_seconds)).where(
            TestAttempt.user_id == user_id,
            TestAttempt.status == "completed",
        )
    )
    return {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "total_points": float(analytics.total_points) if analytics is not None and analytics.total_points is not None else 0.0,
        "tests_taken": int(analytics.tests_taken) if analytics is not None and analytics.tests_taken is not None else 0,
        "streak_days": int(analytics.streak_days) if analytics is not None and analytics.streak_days is not None else 0,
        "current_level_id": int(analytics.current_level_id) if analytics is not None and analytics.current_level_id is not None else None,
        "completed_attempts": completed_attempts,
        "avg_score": float(avg_score) if avg_score is not None else None,
        "avg_time_seconds": float(avg_time) if avg_time is not None else None,
        "last_active": analytics.last_active if analytics is not None else None,
    }


async def group_summary(session: AsyncSession, group_id: int) -> Dict[str, Any]:
    member_ids_subquery = select(GroupMembership.user_id).where(GroupMembership.group_id == group_id)

    members_count = int(await session.scalar(select(func.count(GroupMembership.id)).where(GroupMembership.group_id == group_id)) or 0)
    active_members_7d = int(
        await session.scalar(
            select(func.count(func.distinct(Answer.user_id))).where(
                Answer.user_id.in_(member_ids_subquery),
                Answer.created_at >= func.now() - text("interval '7 days'"),
            )
        ) or 0
    )
    total_points = await session.scalar(
        select(func.coalesce(func.sum(Analytics.total_points), 0)).where(Analytics.user_id.in_(member_ids_subquery))
    )
    avg_points = await session.scalar(select(func.avg(Analytics.total_points)).where(Analytics.user_id.in_(member_ids_subquery)))
    completed_attempts = int(
        await session.scalar(
            select(func.count(TestAttempt.id)).where(
                TestAttempt.user_id.in_(member_ids_subquery),
                TestAttempt.status == "completed",
            )
        ) or 0
    )
    avg_score = await session.scalar(
        select(func.avg(TestAttempt.score)).where(
            TestAttempt.user_id.in_(member_ids_subquery),
            TestAttempt.status == "completed",
        )
    )
    avg_time = await session.scalar(
        select(func.avg(TestAttempt.time_spent_seconds)).where(
            TestAttempt.user_id.in_(member_ids_subquery),
            TestAttempt.status == "completed",
        )
    )
    avg_completed_attempts = (completed_attempts / members_count) if members_count else None

    return {
        "group_id": group_id,
        "members_count": members_count,
        "active_members_7d": active_members_7d,
        "total_points": float(total_points or 0.0),
        "avg_points": float(avg_points) if avg_points is not None else None,
        "completed_attempts": completed_attempts,
        "avg_completed_attempts": float(avg_completed_attempts) if avg_completed_attempts is not None else None,
        "avg_score": float(avg_score) if avg_score is not None else None,
        "avg_time_seconds": float(avg_time) if avg_time is not None else None,
    }


async def group_member_performance(session: AsyncSession, group_id: int) -> List[Dict[str, Any]]:
    stmt = (
        select(User.id)
        .join(GroupMembership, GroupMembership.user_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(User.username.asc())
    )
    user_ids = [row[0] for row in (await session.execute(stmt)).all()]
    result: List[Dict[str, Any]] = []
    for user_id in user_ids:
        performance = await user_performance(session, user_id)
        if performance is not None:
            result.append(performance)
    return result


async def test_score_distribution(session: AsyncSession, test_id: int) -> List[Dict[str, Any]]:
    stmt = select(TestAttempt.score, TestAttempt.max_score).where(
        TestAttempt.test_id == test_id,
        TestAttempt.status == "completed",
    )
    rows = (await session.execute(stmt)).all()
    buckets = [
        {"label": "0-19%", "count": 0},
        {"label": "20-39%", "count": 0},
        {"label": "40-59%", "count": 0},
        {"label": "60-79%", "count": 0},
        {"label": "80-100%", "count": 0},
    ]
    for score, max_score in rows:
        if not max_score or max_score <= 0:
            percent = 0.0
        else:
            percent = max(0.0, min(100.0, (float(score or 0.0) / float(max_score)) * 100.0))
        index = min(int(percent // 20), 4)
        buckets[index]["count"] += 1
    return buckets

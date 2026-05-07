from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import case, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement_definition import AchievementDefinition
from app.models.analytics import Analytics
from app.models.answer import Answer
from app.models.group import GroupMembership
from app.models.level import Level
from app.models.material import Material
from app.models.points_ledger import PointsLedger
from app.models.question import Question
from app.models.season import Season
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.cache.redis_cache import NS_LEADERBOARD, NS_TEST_SUMMARY, bump_cache_namespace
from app.repositories import level_repo
from app.services import reward_service


DEFAULT_ACHIEVEMENT_DEFINITIONS = [
    {
        "code": "first_steps",
        "title": "First Steps",
        "description": "Complete your first test attempt.",
        "reward": "Unlock your first achievement badge.",
        "criteria_type": "completed_attempts",
        "threshold_value": 1,
    },
    {
        "code": "focused_three",
        "title": "3-Day Streak",
        "description": "Stay active for 3 consecutive days.",
        "reward": "Showcase consistency in your profile.",
        "criteria_type": "streak_days",
        "threshold_value": 3,
    },
    {
        "code": "focused_week",
        "title": "7-Day Streak",
        "description": "Stay active for 7 consecutive days.",
        "reward": "Highlight long-running learning momentum.",
        "criteria_type": "streak_days",
        "threshold_value": 7,
    },
    {
        "code": "century_points",
        "title": "100 Points",
        "description": "Earn at least 100 total points.",
        "reward": "Prove solid progress in the course.",
        "criteria_type": "total_points",
        "threshold_value": 100,
    },
    {
        "code": "test_marathon",
        "title": "5 Completed Tests",
        "description": "Finish 5 test attempts.",
        "reward": "Unlock marathon learner status.",
        "criteria_type": "completed_attempts",
        "threshold_value": 5,
    },
]


async def get_analytics_for_user(session: AsyncSession, user_id: int) -> Optional[Analytics]:
    q = select(Analytics).where(Analytics.user_id == user_id)
    res = await session.execute(q)
    return res.scalars().first()


def _recalculate_streak(last_active: datetime | None, previous_streak: int, now: datetime) -> int:
    if last_active is None:
        return 1
    if last_active.date() == now.date():
        return max(int(previous_streak or 0), 1)
    day_gap = (now.date() - last_active.date()).days
    if day_gap <= 1:
        return max(int(previous_streak or 0), 0) + 1
    return 1


async def _sync_level_and_activity(session: AsyncSession, analytics: Analytics, *, mark_active: bool) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    if mark_active:
        analytics.streak_days = _recalculate_streak(analytics.last_active, int(analytics.streak_days or 0), now)
        analytics.last_active = now
    current_level = await level_repo.get_current_level_for_points(session, float(analytics.total_points or 0.0))
    analytics.current_level_id = current_level.id if current_level is not None else None


async def _get_or_create_analytics(session: AsyncSession, user_id: int) -> Analytics:
    analytics = await get_analytics_for_user(session, user_id)
    if analytics is None:
        analytics = Analytics(
            user_id=user_id,
            total_points=0.0,
            tests_taken=0,
            last_active=None,
            streak_days=0,
        )
        session.add(analytics)
        await session.flush()
    return analytics


async def _seed_default_achievement_definitions_if_empty(session: AsyncSession) -> None:
    count = int(await session.scalar(select(func.count(AchievementDefinition.id))) or 0)
    if count > 0:
        return
    for item in DEFAULT_ACHIEVEMENT_DEFINITIONS:
        session.add(
            AchievementDefinition(
                code=item["code"],
                title=item["title"],
                description=item["description"],
                reward=item["reward"],
                criteria_type=item["criteria_type"],
                threshold_value=int(item["threshold_value"]),
                is_active=True,
            )
        )
    await session.flush()


async def _list_active_achievement_definitions(session: AsyncSession) -> List[AchievementDefinition]:
    await _seed_default_achievement_definitions_if_empty(session)
    stmt = (
        select(AchievementDefinition)
        .where(AchievementDefinition.is_active.is_(True))
        .order_by(AchievementDefinition.threshold_value.asc(), AchievementDefinition.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def _count_completed_attempts(session: AsyncSession, user_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count(TestAttempt.id)).where(
                TestAttempt.user_id == user_id,
                TestAttempt.status == "completed",
            )
        ) or 0
    )


def _is_achievement_earned(
    definition: AchievementDefinition,
    *,
    total_points: float,
    streak_days: int,
    completed_attempts: int,
) -> bool:
    threshold = int(definition.threshold_value or 0)
    if definition.criteria_type == "total_points":
        return float(total_points) >= float(threshold)
    if definition.criteria_type == "streak_days":
        return int(streak_days) >= threshold
    if definition.criteria_type == "completed_attempts":
        return int(completed_attempts) >= threshold
    return False


async def _award_achievements_if_eligible(
    session: AsyncSession,
    *,
    user_id: int,
    analytics: Analytics,
    source_event: str | None,
) -> None:
    definitions = await _list_active_achievement_definitions(session)
    if not definitions:
        return

    earned_achievement_ids = set(
        (await session.execute(select(UserAchievement.achievement_id).where(UserAchievement.user_id == user_id)))
        .scalars()
        .all()
    )
    completed_attempts = await _count_completed_attempts(session, user_id)
    total_points = float(analytics.total_points or 0.0)
    streak_days = int(analytics.streak_days or 0)

    for definition in definitions:
        if definition.id in earned_achievement_ids:
            continue
        if not _is_achievement_earned(
            definition,
            total_points=total_points,
            streak_days=streak_days,
            completed_attempts=completed_attempts,
        ):
            continue
        session.add(
            UserAchievement(
                user_id=user_id,
                achievement_id=definition.id,
                source_event=source_event,
            )
        )
    await session.flush()


async def apply_points_transaction(
    session: AsyncSession,
    *,
    user_id: int,
    points_delta: float = 0.0,
    mark_active: bool = False,
    tests_delta: int = 0,
    reason_code: str,
    source_type: str | None = None,
    source_id: int | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Analytics:
    if idempotency_key:
        existing = (
            await session.execute(
                select(PointsLedger.id).where(PointsLedger.idempotency_key == idempotency_key).limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await _get_or_create_analytics(session, user_id)

    analytics = await _get_or_create_analytics(session, user_id)
    analytics.total_points = float(analytics.total_points or 0.0) + float(points_delta)
    if tests_delta != 0:
        analytics.tests_taken = max(int(analytics.tests_taken or 0) + int(tests_delta), 0)
    await _sync_level_and_activity(session, analytics, mark_active=mark_active)

    should_write_ledger = bool(idempotency_key) or float(points_delta) != 0.0
    if should_write_ledger:
        session.add(
            PointsLedger(
                user_id=user_id,
                delta=float(points_delta),
                reason_code=reason_code,
                source_type=source_type,
                source_id=source_id,
                idempotency_key=idempotency_key,
                metadata_json=metadata,
            )
        )

    await _award_achievements_if_eligible(session, user_id=user_id, analytics=analytics, source_event=reason_code)
    await reward_service.sync_user_rewards(session, user_id)
    await session.flush()
    try:
        await bump_cache_namespace(NS_LEADERBOARD, NS_TEST_SUMMARY)
    except Exception:
        # Cache invalidation failures must not break transactional updates.
        pass
    return analytics


async def create_or_update_analytics(
    session: AsyncSession,
    user_id: int,
    points_delta: float = 0.0,
    mark_active: bool = False,
    tests_delta: int = 0,
    reason_code: str = "analytics_update",
    source_type: str | None = None,
    source_id: int | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Analytics:
    return await apply_points_transaction(
        session,
        user_id=user_id,
        points_delta=points_delta,
        mark_active=mark_active,
        tests_delta=tests_delta,
        reason_code=reason_code,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


async def get_user_analytics(session: AsyncSession, user_id: int) -> Optional[Analytics]:
    return await get_analytics_for_user(session, user_id)


async def get_access_points_for_user(session: AsyncSession, user_id: int) -> float:
    """
    Effective access points for level gating.

    Rules:
    - take score of the latest completed attempt per test;
    - if no completed attempts exist for a test, fallback to legacy answers
      (rows with attempt_id IS NULL) for backward compatibility.
    """
    latest_completed_subquery = (
        select(
            TestAttempt.test_id.label("test_id"),
            func.coalesce(TestAttempt.score, 0.0).label("score"),
            func.row_number()
            .over(
                partition_by=TestAttempt.test_id,
                order_by=(TestAttempt.completed_at.desc(), TestAttempt.id.desc()),
            )
            .label("row_num"),
        )
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.status == "completed",
        )
        .subquery()
    )
    latest_completed_rows = (
        await session.execute(
            select(
                latest_completed_subquery.c.test_id,
                latest_completed_subquery.c.score,
            ).where(latest_completed_subquery.c.row_num == 1)
        )
    ).all()
    latest_scores_by_test = {
        int(test_id): float(score or 0.0)
        for test_id, score in latest_completed_rows
    }

    legacy_scores_rows = (
        await session.execute(
            select(
                Answer.test_id,
                func.coalesce(func.sum(Answer.score), 0.0).label("score_sum"),
            )
            .where(
                Answer.user_id == user_id,
                Answer.attempt_id.is_(None),
            )
            .group_by(Answer.test_id)
        )
    ).all()

    effective_points = sum(latest_scores_by_test.values())
    for test_id, score_sum in legacy_scores_rows:
        normalized_test_id = int(test_id)
        if normalized_test_id in latest_scores_by_test:
            continue
        effective_points += float(score_sum or 0.0)

    return max(float(effective_points), 0.0)


async def apply_points_delta(
    session: AsyncSession,
    user_id: int,
    points_delta: float,
    *,
    reason_code: str = "points_adjustment",
    source_type: str | None = None,
    source_id: int | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Analytics:
    return await apply_points_transaction(
        session,
        user_id=user_id,
        points_delta=points_delta,
        mark_active=False,
        tests_delta=0,
        reason_code=reason_code,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


async def register_completed_attempt(session: AsyncSession, user_id: int, attempt_id: int | None = None) -> Analytics:
    return await create_or_update_analytics(
        session,
        user_id=user_id,
        points_delta=0.0,
        mark_active=True,
        tests_delta=1,
        reason_code="attempt_completed",
        source_type="test_attempt",
        source_id=attempt_id,
        idempotency_key=f"attempt_completed:{attempt_id}" if attempt_id is not None else None,
    )


async def list_user_achievements(session: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    definitions = await _list_active_achievement_definitions(session)
    earned_rows = (
        await session.execute(
            select(
                AchievementDefinition.code,
                UserAchievement.earned_at,
            )
            .join(UserAchievement, UserAchievement.achievement_id == AchievementDefinition.id)
            .where(UserAchievement.user_id == user_id)
        )
    ).all()
    earned_map = {code: earned_at for code, earned_at in earned_rows}

    items: List[Dict[str, Any]] = []
    for definition in definitions:
        earned_at = earned_map.get(definition.code)
        items.append(
            {
                "code": definition.code,
                "title": definition.title,
                "description": definition.description,
                "reward": definition.reward,
                "criteria_type": definition.criteria_type,
                "threshold_value": int(definition.threshold_value),
                "earned": earned_at is not None,
                "earned_at": earned_at,
            }
        )
    return items


async def list_points_ledger_for_user(
    session: AsyncSession,
    user_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    stmt = (
        select(PointsLedger)
        .where(PointsLedger.user_id == user_id)
        .order_by(PointsLedger.id.desc())
        .limit(max(int(limit), 1))
        .offset(max(int(offset), 0))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_points_ledger_to_read_dict(row) for row in rows]


def _points_ledger_to_read_dict(row: PointsLedger) -> Dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "delta": float(row.delta or 0.0),
        "reason_code": row.reason_code,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "idempotency_key": row.idempotency_key,
        "metadata": row.metadata_json or {},
        "created_at": row.created_at,
    }


async def get_gamification_progress(session: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    analytics = await get_user_analytics(session, user_id)
    user = await session.get(User, user_id)
    if user is None:
        return None

    total_points = float(analytics.total_points) if analytics is not None and analytics.total_points is not None else 0.0
    streak_days = int(analytics.streak_days) if analytics is not None and analytics.streak_days is not None else 0
    completed_attempts = await _count_completed_attempts(session, user_id)
    current_level = await level_repo.get_current_level_for_points(session, total_points)
    next_level = await level_repo.get_next_level_for_points(session, total_points)
    achievements = await list_user_achievements(session, user_id)
    badges = [
        {
            "code": achievement["code"],
            "title": achievement["title"],
            "description": achievement["description"],
            "reward": achievement["reward"],
            "earned": achievement["earned"],
        }
        for achievement in achievements
    ]
    earned_badges_count = sum(1 for badge in badges if badge["earned"])

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
        "completed_attempts": completed_attempts,
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
        "earned_badges_count": earned_badges_count,
        "badges": badges,
    }


async def get_leaderboard(session: AsyncSession, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    return await get_leaderboard_scoped(
        session,
        limit=limit,
        offset=offset,
        scope="global",
        period="all_time",
        group_id=None,
        season_id=None,
    )


async def _resolve_leaderboard_period_window(
    session: AsyncSession,
    *,
    period: str,
    season_id: int | None,
) -> tuple[datetime | None, datetime | None]:
    now = datetime.now(UTC).replace(tzinfo=None)
    if period == "all_time":
        return None, None
    if period == "week":
        return now - timedelta(days=7), now
    if period == "season":
        if season_id is None:
            raise ValueError("season_id is required for period=season")
        season = await session.get(Season, season_id)
        if season is None:
            raise LookupError("Season not found")
        return season.starts_at, season.ends_at
    raise ValueError("Unsupported leaderboard period")


async def get_leaderboard_scoped(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    scope: str = "global",
    period: str = "all_time",
    group_id: int | None = None,
    season_id: int | None = None,
) -> List[Dict[str, Any]]:
    if scope not in {"global", "group"}:
        raise ValueError("Unsupported leaderboard scope")
    if scope == "group" and group_id is None:
        raise ValueError("group_id is required for scope=group")

    window_start, window_end = await _resolve_leaderboard_period_window(
        session,
        period=period,
        season_id=season_id,
    )

    if period == "all_time":
        points_expr = func.coalesce(Analytics.total_points, 0.0)
        stmt = select(
            User.id.label("user_id"),
            User.username.label("username"),
            points_expr.label("total_points"),
        ).outerjoin(Analytics, Analytics.user_id == User.id)
    else:
        ledger_stmt = select(
            PointsLedger.user_id.label("user_id"),
            func.coalesce(func.sum(PointsLedger.delta), 0.0).label("period_points"),
        )
        if window_start is not None:
            ledger_stmt = ledger_stmt.where(PointsLedger.created_at >= window_start)
        if window_end is not None:
            ledger_stmt = ledger_stmt.where(PointsLedger.created_at <= window_end)
        ledger_subq = ledger_stmt.group_by(PointsLedger.user_id).subquery()
        points_expr = func.coalesce(ledger_subq.c.period_points, 0.0)
        stmt = select(
            User.id.label("user_id"),
            User.username.label("username"),
            points_expr.label("total_points"),
        ).outerjoin(ledger_subq, ledger_subq.c.user_id == User.id)

    if scope == "group":
        stmt = stmt.join(GroupMembership, GroupMembership.user_id == User.id).where(GroupMembership.group_id == group_id)

    stmt = stmt.order_by(desc(points_expr), User.id.asc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "user_id": row.user_id,
            "username": row.username,
            "total_points": float(row.total_points or 0.0),
        }
        for row in rows
    ]


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
    attempts_agg = (
        select(
            TestAttempt.user_id.label("user_id"),
            func.sum(case((TestAttempt.status == "completed", 1), else_=0)).label("completed_attempts"),
            func.avg(case((TestAttempt.status == "completed", TestAttempt.score), else_=None)).label("avg_score"),
            func.avg(case((TestAttempt.status == "completed", TestAttempt.time_spent_seconds), else_=None)).label(
                "avg_time_seconds"
            ),
        )
        .group_by(TestAttempt.user_id)
        .subquery()
    )
    stmt = (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            User.full_name.label("full_name"),
            Analytics.total_points.label("total_points"),
            Analytics.tests_taken.label("tests_taken"),
            Analytics.streak_days.label("streak_days"),
            Analytics.current_level_id.label("current_level_id"),
            Analytics.last_active.label("last_active"),
            attempts_agg.c.completed_attempts.label("completed_attempts"),
            attempts_agg.c.avg_score.label("avg_score"),
            attempts_agg.c.avg_time_seconds.label("avg_time_seconds"),
        )
        .join(GroupMembership, GroupMembership.user_id == User.id)
        .outerjoin(Analytics, Analytics.user_id == User.id)
        .outerjoin(attempts_agg, attempts_agg.c.user_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(User.username.asc())
    )
    rows = (await session.execute(stmt)).mappings().all()
    return [
        {
            "user_id": row["user_id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "total_points": float(row["total_points"] or 0.0),
            "tests_taken": int(row["tests_taken"] or 0),
            "streak_days": int(row["streak_days"] or 0),
            "current_level_id": int(row["current_level_id"]) if row["current_level_id"] is not None else None,
            "completed_attempts": int(row["completed_attempts"] or 0),
            "avg_score": float(row["avg_score"]) if row["avg_score"] is not None else None,
            "avg_time_seconds": float(row["avg_time_seconds"]) if row["avg_time_seconds"] is not None else None,
            "last_active": row["last_active"],
        }
        for row in rows
    ]


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

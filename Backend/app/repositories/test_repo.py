from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.core.test_attempts import build_attempt_view_state, is_deadline_passed, utcnow_naive
from app.models.answer import Answer
from app.models.question import Question
from app.models.test_ import Test
from app.models.material import Material
from app.models.test_attempt import TestAttempt

_UNSET = object()


async def _load_materials_by_ids(session, material_ids: list[int]) -> list[Material]:
    if not material_ids:
        return []
    rows = (
        await session.execute(select(Material).where(Material.id.in_(material_ids)))
    ).scalars().all()
    order_index = {material_id: idx for idx, material_id in enumerate(material_ids)}
    return sorted(rows, key=lambda item: order_index.get(item.id, 10**9))


async def _sync_test_material_links(
    session,
    test: Test,
    *,
    material_ids: list[int] | None = None,
) -> None:
    resolved_material_ids = list(dict.fromkeys([mid for mid in (material_ids or []) if mid is not None]))
    materials = await _load_materials_by_ids(session, resolved_material_ids)
    test.materials = materials


async def get_test(session, test_id: int):
    q = select(Test).options(selectinload(Test.materials), selectinload(Test.required_level)).where(Test.id == test_id)
    res = await session.execute(q)
    return res.scalars().first()

async def list_tests(
    session,
    published_only: bool = True,
    limit: int = 100,
    author_id: int | None = None,
):
    q = select(Test).options(selectinload(Test.materials), selectinload(Test.required_level))
    if published_only:
        q = q.where(Test.published == True)
    if author_id is not None:
        q = q.where(Test.author_id == author_id)
    q = q.limit(limit)
    res = await session.execute(q)
    return res.scalars().all()


async def get_user_test_state_map(
    session,
    *,
    user_id: int,
    tests: list[Test],
) -> dict[int, dict[str, Any]]:
    if not tests:
        return {}

    tests_by_id = {int(test.id): test for test in tests}
    test_ids = list(tests_by_id.keys())

    question_counts_rows = (
        await session.execute(
            select(Question.test_id, func.count(Question.id))
            .where(Question.test_id.in_(test_ids))
            .group_by(Question.test_id)
        )
    ).all()
    question_counts = {int(test_id): int(total or 0) for test_id, total in question_counts_rows}

    attempts_rows = (
        await session.execute(
            select(
                TestAttempt.test_id,
                func.sum(case((TestAttempt.status == "completed", 1), else_=0)).label("completed_attempts"),
                func.max(case((TestAttempt.status == "in_progress", TestAttempt.id), else_=None)).label(
                    "active_attempt_id"
                ),
            )
            .where(
                TestAttempt.user_id == user_id,
                TestAttempt.test_id.in_(test_ids),
            )
            .group_by(TestAttempt.test_id)
        )
    ).all()
    attempts_map = {
        int(test_id): {
            "completed_attempts": int(completed_attempts or 0),
            "active_attempt_id": int(active_attempt_id) if active_attempt_id is not None else None,
        }
        for test_id, completed_attempts, active_attempt_id in attempts_rows
    }

    latest_completed_subquery = (
        select(
            TestAttempt.test_id.label("test_id"),
            TestAttempt.score.label("score"),
            TestAttempt.max_score.label("max_score"),
            TestAttempt.completed_at.label("completed_at"),
            func.row_number()
            .over(
                partition_by=TestAttempt.test_id,
                order_by=(TestAttempt.completed_at.desc(), TestAttempt.id.desc()),
            )
            .label("row_num"),
        )
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.test_id.in_(test_ids),
            TestAttempt.status == "completed",
        )
        .subquery()
    )
    latest_completed_rows = (
        await session.execute(
            select(
                latest_completed_subquery.c.test_id,
                latest_completed_subquery.c.score,
                latest_completed_subquery.c.max_score,
                latest_completed_subquery.c.completed_at,
            ).where(latest_completed_subquery.c.row_num == 1)
        )
    ).all()
    latest_completed_map = {
        int(test_id): {
            "score": float(score) if score is not None else None,
            "max_score": float(max_score) if max_score is not None else None,
            "completed_at": completed_at,
        }
        for test_id, score, max_score, completed_at in latest_completed_rows
    }

    legacy_answers_rows = (
        await session.execute(
            select(
                Answer.test_id,
                func.count(Answer.id).label("answers_count"),
                func.coalesce(func.sum(Answer.score), 0).label("score_sum"),
            )
            .where(
                Answer.user_id == user_id,
                Answer.test_id.in_(test_ids),
                Answer.attempt_id.is_(None),
            )
            .group_by(Answer.test_id)
        )
    ).all()
    legacy_answers_map = {
        int(test_id): {
            "answers_count": int(answers_count or 0),
            "score_sum": float(score_sum or 0.0),
        }
        for test_id, answers_count, score_sum in legacy_answers_rows
    }

    result: dict[int, dict[str, Any]] = {}
    now = utcnow_naive()
    for test_id in test_ids:
        test = tests_by_id[test_id]

        attempts_data = attempts_map.get(test_id, {})
        completed_attempts = int(attempts_data.get("completed_attempts") or 0)
        active_attempt_id = attempts_data.get("active_attempt_id")

        legacy_answers = legacy_answers_map.get(test_id, {})
        has_legacy_answers = int(legacy_answers.get("answers_count") or 0) > 0
        if completed_attempts == 0 and has_legacy_answers:
            # Backward-compatible fallback for datasets created before attempt tracking.
            completed_attempts = 1

        latest_completed = latest_completed_map.get(test_id, {})
        user_score = latest_completed.get("score")
        user_max_score = latest_completed.get("max_score")
        latest_completed_at = latest_completed.get("completed_at")

        if user_score is None and has_legacy_answers:
            user_score = float(legacy_answers.get("score_sum") or 0.0)
            if test.max_score is not None:
                user_max_score = float(test.max_score)

        attempt_view_state = build_attempt_view_state(
            max_attempts=test.max_attempts,
            completed_attempts=completed_attempts,
            has_active_attempt=active_attempt_id is not None,
            deadline_passed=is_deadline_passed(test.deadline, now=now),
        )

        result[test_id] = {
            "total_questions": int(question_counts.get(test_id, 0)),
            "user_status": attempt_view_state["user_status"],
            "ui_status": attempt_view_state["ui_status"],
            "progress_state": attempt_view_state["progress_state"],
            "attempt_state": attempt_view_state["attempt_state"],
            "can_start": attempt_view_state["can_start"],
            "can_resume": attempt_view_state["can_resume"],
            "block_reason": attempt_view_state["block_reason"],
            "has_active_attempt": active_attempt_id is not None,
            "active_attempt_id": active_attempt_id,
            "completed_attempts": completed_attempts,
            "remaining_attempts": attempt_view_state["remaining_attempts"],
            "max_attempts": attempt_view_state["max_attempts"],
            "user_score": float(user_score) if user_score is not None else None,
            "user_max_score": float(user_max_score) if user_max_score is not None else None,
            "latest_completed_at": latest_completed_at,
        }

    return result

async def create_test(
    session,
    title: str,
    description: str | None = None,
    time_limit_minutes: int | None = None,
    max_score: int | None = None,
    max_attempts: int = 1,
    published: bool = False,
    material_ids: list[int] | None = None,
    deadline=None,
    author_id: int | None = None,
    required_level_id: int | None = None,
):
    test = Test(
        title=title,
        description=description,
        time_limit_minutes=time_limit_minutes,
        max_score=max_score,
        max_attempts=max_attempts,
        published=published,
        deadline=deadline,
        author_id=author_id,
        required_level_id=required_level_id,
    )
    session.add(test)
    await session.flush()

    loaded_test = await get_test(session, test.id)
    if loaded_test is None:
        return test

    await _sync_test_material_links(
        session,
        loaded_test,
        material_ids=material_ids,
    )
    await session.flush()
    await session.refresh(loaded_test)
    return loaded_test


async def update_test(
    session,
    test_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    time_limit_minutes: int | None = None,
    max_score: int | None = None,
    max_attempts: int | None = None,
    published: bool | None = None,
    material_ids: list[int] | None | object = _UNSET,
    deadline: object = _UNSET,
    required_level_id: int | None | object = _UNSET,
):
    test = await get_test(session, test_id)
    if test is None:
        return None

    if title is not None:
        test.title = title
    if description is not None:
        test.description = description
    if time_limit_minutes is not None:
        test.time_limit_minutes = time_limit_minutes
    if max_score is not None:
        test.max_score = max_score
    if max_attempts is not None:
        test.max_attempts = max_attempts
    if published is not None:
        test.published = published
    if deadline is not _UNSET:
        test.deadline = deadline
    if required_level_id is not _UNSET:
        test.required_level_id = required_level_id
    if material_ids is not _UNSET:
        await _sync_test_material_links(
            session,
            test,
            material_ids=material_ids,
        )

    await session.flush()
    await session.refresh(test)
    return test


async def delete_test(session, test_id: int) -> bool:
    test = await get_test(session, test_id)
    if test is None:
        return False
    await session.delete(test)
    await session.flush()
    return True

async def get_test_summary(session, test_id: int):
    """
    Return summary stats for a test:
    - total_questions
    - total_attempts (answers)
    - avg_score_per_attempt (overall)
    - completion_rate (approx)
    """
    attempts_agg = (
        select(
            func.count(TestAttempt.id).label("total_attempts"),
            func.sum(case((TestAttempt.status == "completed", 1), else_=0)).label("completed_attempts"),
            func.avg(case((TestAttempt.status == "completed", TestAttempt.score), else_=None)).label("avg_score"),
            func.avg(case((TestAttempt.status == "completed", TestAttempt.time_spent_seconds), else_=None)).label(
                "avg_time_seconds"
            ),
        )
        .where(TestAttempt.test_id == test_id)
        .subquery()
    )
    answers_agg = (
        select(
            func.count(func.distinct(Answer.attempt_id)).label("fallback_attempts"),
            func.avg(Answer.score).label("fallback_avg_score"),
        )
        .where(
            Answer.test_id == test_id,
            Answer.attempt_id.is_not(None),
        )
        .subquery()
    )
    stmt = select(
        select(func.count(Question.id)).where(Question.test_id == test_id).scalar_subquery().label("total_questions"),
        attempts_agg.c.total_attempts,
        attempts_agg.c.completed_attempts,
        attempts_agg.c.avg_score,
        attempts_agg.c.avg_time_seconds,
        answers_agg.c.fallback_attempts,
        answers_agg.c.fallback_avg_score,
    )
    row = (await session.execute(stmt)).mappings().first()
    total_q = int(row["total_questions"] or 0)
    total_attempts = int(row["total_attempts"] or 0)
    if total_attempts == 0:
        total_attempts = int(row["fallback_attempts"] or 0)
    completed_attempts = int(row["completed_attempts"] or 0)
    avg_score = row["avg_score"]
    if avg_score is None:
        avg_score = row["fallback_avg_score"]
    avg_time = row["avg_time_seconds"]
    return {
        "test_id": test_id,
        "total_questions": total_q,
        "total_attempts": total_attempts,
        "completed_attempts": completed_attempts,
        "avg_score": float(avg_score) if avg_score is not None else None,
        "avg_time_seconds": float(avg_time) if avg_time is not None else None,
    }

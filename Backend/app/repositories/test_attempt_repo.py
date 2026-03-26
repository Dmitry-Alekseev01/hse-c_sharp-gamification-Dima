from datetime import datetime

from sqlalchemy import func, select

from app.models.answer import Answer
from app.models.question import Question
from app.models.test_attempt import TestAttempt


async def create_attempt(session, user_id: int, test_id: int) -> TestAttempt:
    attempt = TestAttempt(user_id=user_id, test_id=test_id, status="in_progress")
    session.add(attempt)
    await session.flush()
    await session.refresh(attempt)
    return attempt


async def get_attempt(session, attempt_id: int) -> TestAttempt | None:
    return await session.get(TestAttempt, attempt_id)


async def get_active_attempt(session, user_id: int, test_id: int) -> TestAttempt | None:
    stmt = (
        select(TestAttempt)
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.test_id == test_id,
            TestAttempt.status == "in_progress",
        )
        .order_by(TestAttempt.started_at.desc(), TestAttempt.id.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalars().first()


async def list_attempts_for_user(session, user_id: int, test_id: int | None = None):
    stmt = select(TestAttempt).where(TestAttempt.user_id == user_id).order_by(TestAttempt.started_at.desc(), TestAttempt.id.desc())
    if test_id is not None:
        stmt = stmt.where(TestAttempt.test_id == test_id)
    res = await session.execute(stmt)
    return res.scalars().all()


async def complete_attempt(session, attempt: TestAttempt) -> TestAttempt:
    if attempt.status != "completed":
        now = datetime.utcnow()
        time_spent_seconds = None
        if attempt.started_at is not None:
            time_spent_seconds = max(int((now - attempt.started_at).total_seconds()), 0)
        attempt.status = "completed"
        attempt.submitted_at = now
        attempt.completed_at = now
        attempt.time_spent_seconds = time_spent_seconds

    return await refresh_attempt_scores(session, attempt)


async def refresh_attempt_scores(session, attempt: TestAttempt) -> TestAttempt:
    score_stmt = select(func.coalesce(func.sum(Answer.score), 0)).where(Answer.attempt_id == attempt.id)
    score_value = await session.scalar(score_stmt)
    max_score_stmt = select(func.coalesce(func.sum(Question.points), 0)).where(Question.test_id == attempt.test_id)
    max_score_value = await session.scalar(max_score_stmt)

    attempt.score = float(score_value or 0)
    attempt.max_score = float(max_score_value or 0)
    await session.flush()
    await session.refresh(attempt)
    return attempt

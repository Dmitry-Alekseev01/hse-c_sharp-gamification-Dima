from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.repositories import analytics_repo, test_attempt_repo
from app.services.challenge_service import ChallengeEventType, record_event


class AttemptPolicyError(ValueError):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


def _is_active_attempt_unique_violation(exc: IntegrityError) -> bool:
    text = str(getattr(exc, "orig", exc))
    return "ux_test_attempts_active_user_test" in text


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def is_deadline_passed(test: Test, now: datetime | None = None) -> bool:
    if test.deadline is None:
        return False
    return (now or utcnow()) >= test.deadline


def is_time_limit_exceeded(test: Test, attempt: TestAttempt, now: datetime | None = None) -> bool:
    if not test.time_limit_minutes or attempt.started_at is None:
        return False
    elapsed_seconds = int(((now or utcnow()) - attempt.started_at).total_seconds())
    return elapsed_seconds >= int(test.time_limit_minutes) * 60


async def finalize_attempt_if_expired(session, test: Test, attempt: TestAttempt) -> tuple[TestAttempt, str | None]:
    if attempt.status == "completed":
        return attempt, None

    reason = None
    if is_deadline_passed(test):
        reason = "deadline"
    elif is_time_limit_exceeded(test, attempt):
        reason = "time_limit"

    if reason is None:
        return attempt, None

    completed_attempt = await test_attempt_repo.complete_attempt(session, attempt)
    await analytics_repo.register_completed_attempt(session, completed_attempt.user_id, attempt_id=completed_attempt.id)
    await record_event(
        session,
        user_id=completed_attempt.user_id,
        event_type=ChallengeEventType.ATTEMPT_COMPLETED,
        increment=1,
    )
    await record_event(
        session,
        user_id=completed_attempt.user_id,
        event_type=ChallengeEventType.STREAK_DAY,
        increment=1,
    )
    return completed_attempt, reason


async def resolve_attempt_for_user(session, test: Test, user_id: int, attempt_id: int | None = None) -> TestAttempt:
    test_id = int(test.id)

    if is_deadline_passed(test):
        raise AttemptPolicyError("Test deadline has passed", code="deadline_passed")

    if attempt_id is not None:
        attempt = await test_attempt_repo.get_attempt(session, attempt_id)
        if attempt is None:
            raise LookupError("Attempt not found")
        if attempt.user_id != user_id or attempt.test_id != test.id:
            raise AttemptPolicyError(
                "Attempt does not belong to the specified user/test",
                code="attempt_mismatch",
            )
        if attempt.status == "completed":
            raise AttemptPolicyError("Attempt is already completed", code="attempt_completed")
        _, reason = await finalize_attempt_if_expired(session, test, attempt)
        if reason == "deadline":
            raise AttemptPolicyError("Test deadline has passed", code="deadline_passed")
        if reason == "time_limit":
            raise AttemptPolicyError("Attempt time limit has been exceeded", code="time_limit_exceeded")
        return attempt

    active_attempt = await test_attempt_repo.get_active_attempt(session, user_id, test_id)
    if active_attempt is not None:
        _, reason = await finalize_attempt_if_expired(session, test, active_attempt)
        if reason == "deadline":
            raise AttemptPolicyError("Test deadline has passed", code="deadline_passed")
        if reason == "time_limit":
            raise AttemptPolicyError("Attempt time limit has been exceeded", code="time_limit_exceeded")
        return active_attempt

    max_attempts = int(test.max_attempts or 1)
    completed_attempts = await test_attempt_repo.count_completed_attempts_for_user_test(session, user_id, test_id)
    if completed_attempts >= max(max_attempts, 1):
        raise AttemptPolicyError(
            f"No attempts remaining for this test (completed_attempts={completed_attempts}, max_attempts={max_attempts})",
            code="no_attempts",
        )

    try:
        return await test_attempt_repo.create_attempt(session, user_id, test_id)
    except IntegrityError as exc:
        if not _is_active_attempt_unique_violation(exc):
            raise
        # Race condition: another request created an in-progress attempt first.
        await session.rollback()
        active_attempt = await test_attempt_repo.get_active_attempt(session, user_id, test_id)
        if active_attempt is not None:
            return active_attempt
        raise

from datetime import datetime

from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.repositories import analytics_repo, test_attempt_repo


class AttemptPolicyError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.utcnow()


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
    await analytics_repo.register_completed_attempt(session, completed_attempt.user_id)
    return completed_attempt, reason


async def resolve_attempt_for_user(session, test: Test, user_id: int, attempt_id: int | None = None) -> TestAttempt:
    if is_deadline_passed(test):
        raise AttemptPolicyError("Test deadline has passed")

    if attempt_id is not None:
        attempt = await test_attempt_repo.get_attempt(session, attempt_id)
        if attempt is None:
            raise LookupError("Attempt not found")
        if attempt.user_id != user_id or attempt.test_id != test.id:
            raise AttemptPolicyError("Attempt does not belong to the specified user/test")
        if attempt.status == "completed":
            raise AttemptPolicyError("Attempt is already completed")
        _, reason = await finalize_attempt_if_expired(session, test, attempt)
        if reason == "deadline":
            raise AttemptPolicyError("Test deadline has passed")
        if reason == "time_limit":
            raise AttemptPolicyError("Attempt time limit has been exceeded")
        return attempt

    active_attempt = await test_attempt_repo.get_active_attempt(session, user_id, test.id)
    if active_attempt is not None:
        _, reason = await finalize_attempt_if_expired(session, test, active_attempt)
        if reason == "deadline":
            raise AttemptPolicyError("Test deadline has passed")
        if reason == "time_limit":
            raise AttemptPolicyError("Attempt time limit has been exceeded")
        return active_attempt

    latest_attempt = await test_attempt_repo.get_latest_attempt_for_user_test(session, user_id, test.id)
    if latest_attempt is not None and latest_attempt.status == "completed":
        raise AttemptPolicyError("Test has already been completed")

    return await test_attempt_repo.create_attempt(session, user_id, test.id)

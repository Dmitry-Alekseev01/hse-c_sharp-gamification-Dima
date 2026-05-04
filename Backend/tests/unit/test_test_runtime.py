from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.asyncio

from app.models.answer import Answer
from app.models.choice import Choice
from app.models.question import Question
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.models.user import User
from app.repositories import test_attempt_repo
from app.services.answer_service import submit_answer
from app.services.test_runtime import AttemptPolicyError, finalize_attempt_if_expired, resolve_attempt_for_user


@pytest.mark.asyncio
async def test_resolve_attempt_for_user_blocks_second_completed_attempt(db):
    user = User(username="attempt_user", password_hash="x")
    test = Test(title="single attempt policy")
    db.add_all([user, test])
    await db.flush()

    attempt = await resolve_attempt_for_user(db, test, user.id)
    await test_attempt_repo.complete_attempt(db, attempt)

    with pytest.raises(AttemptPolicyError, match="No attempts remaining"):
        await resolve_attempt_for_user(db, test, user.id)


@pytest.mark.asyncio
async def test_resolve_attempt_for_user_allows_retry_until_max_attempts(db):
    user = User(username="attempt_user_retries", password_hash="x")
    test = Test(title="retry policy", max_attempts=2)
    db.add_all([user, test])
    await db.flush()

    first_attempt = await resolve_attempt_for_user(db, test, user.id)
    await test_attempt_repo.complete_attempt(db, first_attempt)

    second_attempt = await resolve_attempt_for_user(db, test, user.id)
    assert second_attempt.id != first_attempt.id
    await test_attempt_repo.complete_attempt(db, second_attempt)

    with pytest.raises(AttemptPolicyError, match="No attempts remaining"):
        await resolve_attempt_for_user(db, test, user.id)


@pytest.mark.asyncio
async def test_finalize_attempt_if_expired_completes_timed_out_attempt(db):
    user = User(username="timeout_user", password_hash="x")
    test = Test(title="timed", time_limit_minutes=1)
    db.add_all([user, test])
    await db.flush()

    attempt = await test_attempt_repo.create_attempt(db, user.id, test.id)
    attempt.started_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=2)
    await db.flush()

    completed_attempt, reason = await finalize_attempt_if_expired(db, test, attempt)

    assert reason == "time_limit"
    assert completed_attempt.status == "completed"


@pytest.mark.asyncio
async def test_manual_attempt_score_overrides_computed_score(db):
    user = User(username="manual_score_user", password_hash="x")
    test = Test(title="manual score test")
    db.add_all([user, test])
    await db.flush()

    question = Question(test_id=test.id, text="Pick", points=5.0, is_open_answer=False)
    db.add(question)
    await db.flush()

    choice = Choice(question_id=question.id, value="right", ordinal=1, is_correct=True)
    db.add(choice)
    await db.flush()

    attempt = await resolve_attempt_for_user(db, test, user.id)
    await submit_answer(db, user.id, test.id, question.id, str(choice.id), attempt_id=attempt.id)
    attempt = await test_attempt_repo.complete_attempt(db, attempt)
    attempt = await test_attempt_repo.set_manual_score(db, attempt, 3.5)

    assert attempt.score == pytest.approx(3.5)
    assert attempt.manual_score == pytest.approx(3.5)


@pytest.mark.asyncio
async def test_resolve_attempt_for_user_recovers_from_unique_violation_race(db, monkeypatch):
    user = User(username="attempt_user_race", password_hash="x")
    test = Test(title="race policy", max_attempts=2)
    db.add_all([user, test])
    await db.flush()

    fallback_attempt = TestAttempt(id=999, user_id=user.id, test_id=test.id, status="in_progress")
    calls = {"get_active": 0}

    async def fake_get_active_attempt(session, user_id: int, test_id: int):  # noqa: ARG001
        calls["get_active"] += 1
        if calls["get_active"] == 1:
            return None
        return fallback_attempt

    async def fake_create_attempt(session, user_id: int, test_id: int):  # noqa: ARG001
        raise IntegrityError(
            "INSERT INTO test_attempts ...",
            {"user_id": user_id, "test_id": test_id},
            Exception('duplicate key value violates unique constraint "ux_test_attempts_active_user_test"'),
        )

    monkeypatch.setattr(test_attempt_repo, "get_active_attempt", fake_get_active_attempt)
    monkeypatch.setattr(test_attempt_repo, "create_attempt", fake_create_attempt)

    attempt = await resolve_attempt_for_user(db, test, user.id)

    assert attempt is fallback_attempt
    assert calls["get_active"] >= 2


@pytest.mark.asyncio
async def test_resolve_attempt_for_user_reraises_non_target_integrity_error(db, monkeypatch):
    user = User(username="attempt_user_non_target", password_hash="x")
    test = Test(title="non target integrity error", max_attempts=2)
    db.add_all([user, test])
    await db.flush()

    async def fake_get_active_attempt(session, user_id: int, test_id: int):  # noqa: ARG001
        return None

    async def fake_create_attempt(session, user_id: int, test_id: int):  # noqa: ARG001
        raise IntegrityError(
            "INSERT INTO test_attempts ...",
            {"user_id": user_id, "test_id": test_id},
            Exception("some other constraint violation"),
        )

    monkeypatch.setattr(test_attempt_repo, "get_active_attempt", fake_get_active_attempt)
    monkeypatch.setattr(test_attempt_repo, "create_attempt", fake_create_attempt)

    with pytest.raises(IntegrityError):
        await resolve_attempt_for_user(db, test, user.id)

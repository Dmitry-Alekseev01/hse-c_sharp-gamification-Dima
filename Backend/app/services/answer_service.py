"""
Orchestration service for answers:
- persist answer
- try auto-grade (MCQ)
- update analytics
- invalidate cache
- queue open-answer jobs for manual grading
"""
import logging
from datetime import UTC, datetime
import json
from typing import Optional

from app.api.deps import add_post_commit_task
from app.repositories import answer_repo, analytics_repo, test_attempt_repo
from app.models.answer import Answer
from app.models.choice import Choice
from app.models.question import Question
from app.cache.redis_cache import NS_LEADERBOARD, NS_TEST_SUMMARY, bump_cache_namespace, get_redis_client
from app.services.challenge_service import ChallengeEventType, record_event

logger = logging.getLogger(__name__)

async def submit_answer(
    session,
    user_id: int,
    test_id: int,
    question_id: int,
    payload: str,
    attempt_id: int | None = None,
    *,
    validate_attempt: bool = True,
):
    """
    High-level flow:
    1) persist answer
    2) load question to know if open/MCQ
    3) if MCQ -> grade immediately; update analytics
       if open -> push job to redis 'grading:open' and leave score NULL
    4) invalidate caches (leaderboard/test summary/user analytics)
    Returns the Answer object (possibly graded).
    """
    question: Optional[Question] = await session.get(Question, question_id)
    if question is None:
        raise LookupError("Question not found")
    if question.test_id != test_id:
        raise ValueError("Question does not belong to the specified test")
    normalized_payload = "" if payload is None else str(payload)
    trimmed_payload = normalized_payload.strip()

    if attempt_id is not None and validate_attempt:
        attempt = await test_attempt_repo.get_attempt(session, attempt_id)
        if attempt is None:
            raise LookupError("Attempt not found")
        if attempt.user_id != user_id or attempt.test_id != test_id:
            raise ValueError("Attempt does not belong to the specified user/test")
        if attempt.status == "completed":
            raise ValueError("Attempt is already completed")

    is_open = bool(question.is_open_answer)
    skipped_closed_answer = False
    skipped_open_answer = False
    should_enqueue_open_grading = False

    if not is_open:
        if trimmed_payload.lower() in {"", "null", "none"}:
            skipped_closed_answer = True
            normalized_payload = ""
        else:
            try:
                choice_id = int(trimmed_payload)
            except (TypeError, ValueError):
                raise ValueError("Closed question answer must be a valid choice id")
            choice: Optional[Choice] = await session.get(Choice, choice_id)
            if choice is None or choice.question_id != question_id:
                raise ValueError("Selected choice does not belong to the specified question")
    elif trimmed_payload == "":
        skipped_open_answer = True

    # 1) persist or replace an existing answer for the same question slot
    ans, previous_score = await answer_repo.upsert_answer(
        session,
        user_id=user_id,
        test_id=test_id,
        question_id=question_id,
        payload=normalized_payload,
        attempt_id=attempt_id,
    )

    # 3) auto-grade if not open-answer (MCQ)
    graded = None
    points_delta = -previous_score if is_open else 0.0
    if not is_open:
        graded = await answer_repo.grade_mcq_answer(session, ans.id)
        current_score = float(graded.score) if (graded and graded.score is not None) else 0.0
        points_delta = current_score - previous_score
        if skipped_closed_answer and graded is not None and graded.score is None:
            # Keep skipped MCQ explicitly zero-scored for stable attempt aggregation.
            graded.score = 0.0
            await session.flush()
            await session.refresh(graded)
    else:
        if skipped_open_answer:
            # Empty open answer is treated as an intentionally skipped question.
            ans.score = 0.0
            ans.graded_by = None
            ans.graded_at = None
            await session.flush()
            await session.refresh(ans)
        else:
            # Queueing is done post-commit to avoid worker races with uncommitted rows.
            should_enqueue_open_grading = True

    await analytics_repo.create_or_update_analytics(
        session,
        user_id=user_id,
        points_delta=points_delta,
        mark_active=True,
        reason_code="answer_auto_graded" if not is_open else "answer_open_submitted",
        source_type="answer",
        source_id=ans.id,
        metadata={
            "test_id": test_id,
            "question_id": question_id,
            "attempt_id": attempt_id,
            "is_open_answer": is_open,
        },
    )
    await record_event(
        session,
        user_id=user_id,
        event_type=ChallengeEventType.ANSWER_SUBMITTED,
        increment=1,
    )
    await record_event(
        session,
        user_id=user_id,
        event_type=ChallengeEventType.STREAK_DAY,
        increment=1,
    )
    if attempt_id is not None:
        attempt = await test_attempt_repo.get_attempt(session, attempt_id)
        if attempt is not None:
            await test_attempt_repo.refresh_attempt_scores(session, attempt)

    async def invalidate_after_commit() -> None:
        try:
            await bump_cache_namespace(NS_LEADERBOARD, NS_TEST_SUMMARY)
        except Exception:
            pass

    add_post_commit_task(session, invalidate_after_commit)

    if should_enqueue_open_grading:
        async def enqueue_open_grading_after_commit() -> None:
            try:
                r = get_redis_client()
                job = {"answer_id": ans.id, "user_id": user_id}
                await r.rpush("grading:open", json.dumps(job))
            except Exception:
                logger.exception("Failed to enqueue open-answer grading job", extra={"answer_id": ans.id})

        add_post_commit_task(session, enqueue_open_grading_after_commit)

    return graded if graded is not None else ans


async def manual_grade_open_answer(session, answer_id: int, grader_id: int, score: float) -> Answer:
    answer: Optional[Answer] = await session.get(Answer, answer_id)
    if answer is None:
        raise LookupError("Answer not found")

    question: Optional[Question] = await session.get(Question, answer.question_id)
    if question is None:
        raise LookupError("Question not found")
    if not question.is_open_answer:
        raise ValueError("Manual grading is allowed only for open-answer questions")

    max_score = float(question.points)
    normalized_score = float(score)
    if normalized_score < 0 or normalized_score > max_score:
        raise ValueError(f"Score must be between 0 and {max_score}")

    previous_score = float(answer.score or 0.0)
    answer.score = normalized_score
    answer.graded_by = grader_id
    answer.graded_at = datetime.now(UTC).replace(tzinfo=None)
    await session.flush()
    await session.refresh(answer)

    delta = normalized_score - previous_score
    if delta != 0:
        await analytics_repo.apply_points_delta(
            session,
            answer.user_id,
            delta,
            reason_code="answer_manual_grade",
            source_type="answer",
            source_id=answer.id,
            idempotency_key=f"answer_manual_grade:{answer.id}:{normalized_score}",
            metadata={
                "question_id": answer.question_id,
                "attempt_id": answer.attempt_id,
                "grader_id": grader_id,
            },
        )
        if answer.attempt_id is not None:
            attempt = await test_attempt_repo.get_attempt(session, answer.attempt_id)
            if attempt is not None:
                await test_attempt_repo.refresh_attempt_scores(session, attempt)

        try:
            await bump_cache_namespace(NS_LEADERBOARD, NS_TEST_SUMMARY)
        except Exception:
            pass

    return answer

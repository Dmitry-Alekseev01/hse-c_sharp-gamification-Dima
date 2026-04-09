"""
Orchestration service for answers:
- persist answer
- try auto-grade (MCQ)
- update analytics
- invalidate cache
- queue open-answer jobs for manual grading
"""
from datetime import datetime
import json
from typing import Optional

from app.api.deps import add_post_commit_task
from app.repositories import answer_repo, analytics_repo, test_attempt_repo
from app.models.answer import Answer
from app.models.choice import Choice
from app.models.question import Question
from app.cache.redis_cache import NS_LEADERBOARD, NS_TEST_SUMMARY, bump_cache_namespace, get_redis_client


async def submit_answer(session, user_id: int, test_id: int, question_id: int, payload: str, attempt_id: int | None = None):
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

    if attempt_id is not None:
        attempt = await test_attempt_repo.get_attempt(session, attempt_id)
        if attempt is None:
            raise LookupError("Attempt not found")
        if attempt.user_id != user_id or attempt.test_id != test_id:
            raise ValueError("Attempt does not belong to the specified user/test")
        if attempt.status == "completed":
            raise ValueError("Attempt is already completed")

    is_open = bool(question.is_open_answer)

    if not is_open:
        try:
            choice_id = int(str(payload).strip())
        except (TypeError, ValueError):
            raise ValueError("Closed question answer must be a valid choice id")
        choice: Optional[Choice] = await session.get(Choice, choice_id)
        if choice is None or choice.question_id != question_id:
            raise ValueError("Selected choice does not belong to the specified question")

    # 1) persist or replace an existing answer for the same question slot
    ans, previous_score = await answer_repo.upsert_answer(
        session,
        user_id=user_id,
        test_id=test_id,
        question_id=question_id,
        payload=payload,
        attempt_id=attempt_id,
    )

    # 3) auto-grade if not open-answer (MCQ)
    graded = None
    points_delta = -previous_score if is_open else 0.0
    if not is_open:
        graded = await answer_repo.grade_mcq_answer(session, ans.id)
        current_score = float(graded.score) if (graded and graded.score is not None) else 0.0
        points_delta = current_score - previous_score
    else:
        # open answer -> push to redis queue for manual grading
        try:
            r = get_redis_client()
            job = {"answer_id": ans.id, "user_id": user_id}
            await r.rpush("grading:open", json.dumps(job))
        except Exception:
            # if redis queueing fails, continue; the answer remains ungraded
            pass

    await analytics_repo.create_or_update_analytics(
        session,
        user_id=user_id,
        points_delta=points_delta,
        mark_active=True,
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
    answer.graded_at = datetime.utcnow()
    await session.flush()
    await session.refresh(answer)

    delta = normalized_score - previous_score
    if delta != 0:
        await analytics_repo.apply_points_delta(session, answer.user_id, delta)
        if answer.attempt_id is not None:
            attempt = await test_attempt_repo.get_attempt(session, answer.attempt_id)
            if attempt is not None:
                await test_attempt_repo.refresh_attempt_scores(session, attempt)

        try:
            await bump_cache_namespace(NS_LEADERBOARD, NS_TEST_SUMMARY)
        except Exception:
            pass

    return answer

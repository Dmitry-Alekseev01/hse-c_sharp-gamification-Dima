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

from app.repositories import answer_repo, analytics_repo, test_attempt_repo
from app.models.answer import Answer
from app.models.question import Question
from app.cache.redis_cache import get_redis_client, delete_pattern


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
    # 1) persist
    ans = await answer_repo.record_answer(session, user_id, test_id, question_id, payload, attempt_id=attempt_id)

    # 2) load question (to decide open vs MCQ)
    question: Optional[Question] = await session.get(Question, question_id)
    # If we cannot find question, still attempt to grade by payload, but be conservative
    is_open = True if (question is None or question.is_open_answer) else False

    # 3) auto-grade if not open-answer (MCQ)
    graded = None
    if not is_open:
        graded = await answer_repo.grade_mcq_answer(session, ans.id)
        # points (could be None if grader couldn't determine)
        points_awarded = float(graded.score) if (graded and graded.score is not None) else 0.0

        # update analytics incrementally
        try:
            await analytics_repo.create_or_update_analytics(session, user_id, points_delta=points_awarded, mark_active=True)
        except Exception:
            # analytics update failure should not break main flow
            pass
    else:
        # open answer -> push to redis queue for manual grading
        try:
            r = get_redis_client()
            job = {"answer_id": ans.id, "user_id": user_id}
            await r.rpush("grading:open", json.dumps(job))
        except Exception:
            # if redis queueing fails, continue; the answer remains ungraded
            pass

    # 4) invalidate caches (leaderboard + test summary + user analytics)
    try:
        # delete any leaderboard caches
        await delete_pattern("leaderboard:top:*")
        # delete test summary caches for this test
        await delete_pattern(f"test:{test_id}:summary*")
        # delete per-user analytics cache (if you use a naming scheme like user:{id}:analytics)
        await delete_pattern(f"user:{user_id}:analytics*")
    except Exception:
        # don't raise on caching failures
        pass

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

    return answer

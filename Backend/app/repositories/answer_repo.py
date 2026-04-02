"""
Answer repository: persistence + MCQ autograder helper.

Functions:
- record_answer(session, user_id, test_id, question_id, payload)
- grade_mcq_answer(session, answer_id)
- get_answers_for_test(session, test_id, limit=100, offset=0)
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.answer import Answer
from app.models.choice import Choice
from app.models.question import Question
from app.models.test_ import Test


async def record_answer(session, user_id: int, test_id: int, question_id: int, payload: str, attempt_id: int | None = None) -> Answer:
    """
    Persist an Answer row and return it (fresh from DB).
    """
    a = Answer(user_id=user_id, test_id=test_id, attempt_id=attempt_id, question_id=question_id, answer_payload=payload)
    session.add(a)
    await session.flush()
    await session.refresh(a)
    return a


async def get_existing_answer(
    session,
    *,
    user_id: int,
    test_id: int,
    question_id: int,
    attempt_id: int | None,
) -> Answer | None:
    stmt = select(Answer).where(
        Answer.user_id == user_id,
        Answer.test_id == test_id,
        Answer.question_id == question_id,
    )
    if attempt_id is None:
        stmt = stmt.where(Answer.attempt_id.is_(None))
    else:
        stmt = stmt.where(Answer.attempt_id == attempt_id)

    res = await session.execute(stmt.limit(1))
    return res.scalars().first()


async def upsert_answer(
    session,
    *,
    user_id: int,
    test_id: int,
    question_id: int,
    payload: str,
    attempt_id: int | None = None,
) -> tuple[Answer, float]:
    existing = await get_existing_answer(
        session,
        user_id=user_id,
        test_id=test_id,
        question_id=question_id,
        attempt_id=attempt_id,
    )
    if existing is None:
        answer = await record_answer(
            session,
            user_id=user_id,
            test_id=test_id,
            question_id=question_id,
            payload=payload,
            attempt_id=attempt_id,
        )
        return answer, 0.0

    previous_score = float(existing.score or 0.0)
    existing.answer_payload = payload
    existing.score = None
    existing.graded_by = None
    existing.graded_at = None
    await session.flush()
    await session.refresh(existing)
    return existing, previous_score


async def grade_mcq_answer(session, answer_id: int) -> Optional[Answer]:
    """
    Auto-grade answer with MCQ: parses answer.answer_payload as int(choice_id),
    loads Choice and Question and sets score = question.points if choice.is_correct else 0.0.

    Returns the updated Answer (fresh from DB). If cannot auto-grade (bad payload / choice not found),
    returns the Answer unchanged (score may remain None).
    """
    # load the answer first
    answer = await session.get(Answer, answer_id)
    if not answer:
        return None

    payload = answer.answer_payload
    if payload is None:
        # nothing to grade
        return answer

    # try parse as integer choice id
    try:
        choice_id = int(str(payload).strip())
    except (ValueError, TypeError):
        # not an MCQ choice id
        return answer

    stmt = (
        select(Choice, Question)
        .join(Question, Choice.question_id == Question.id)
        .where(Choice.id == choice_id, Question.id == answer.question_id)
    )

    res = await session.execute(stmt)
    row = res.first()

    if not row:
        # choice not found, can't auto-grade
        return answer

    choice_obj, question_obj = row
    # compute score
    score = float(question_obj.points) if bool(choice_obj.is_correct) else 0.0

    # persist score
    answer.score = score
    await session.flush()
    await session.refresh(answer)

    return answer


async def get_answers_for_test(session, test_id: int, limit: int = 100, offset: int = 0):
    stmt = select(Answer).where(Answer.test_id == test_id).limit(limit).offset(offset)
    res = await session.execute(stmt)
    return res.scalars().all()


async def get_pending_open_answers(
    session,
    limit: int = 100,
    offset: int = 0,
    test_id: int | None = None,
    user_id: int | None = None,
    author_id: int | None = None,
):
    stmt = (
        select(Answer)
        .join(Question, Answer.question_id == Question.id)
        .join(Test, Answer.test_id == Test.id)
        .options(selectinload(Answer.question), selectinload(Answer.user))
        .where(Question.is_open_answer.is_(True), Answer.score.is_(None))
        .order_by(Answer.created_at.asc(), Answer.id.asc())
        .limit(limit)
        .offset(offset)
    )
    if test_id is not None:
        stmt = stmt.where(Answer.test_id == test_id)
    if user_id is not None:
        stmt = stmt.where(Answer.user_id == user_id)
    if author_id is not None:
        stmt = stmt.where(Test.author_id == author_id)

    res = await session.execute(stmt)
    return res.scalars().all()

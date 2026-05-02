from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.models.choice import Choice
from app.models.question import Question


async def create_question_with_choices(
    session,
    test_id: int,
    text: str,
    points: float = 1.0,
    is_open_answer: bool = False,
    material_urls: list[str] | None = None,
    choices: list[dict] | None = None,
):
    """
    Creates a Question and its Choices (if provided).
    choices: list of dicts {value, ordinal, is_correct}
    """
    question = Question(
        test_id=test_id,
        text=text,
        points=points,
        is_open_answer=is_open_answer,
        material_urls=material_urls,
    )
    session.add(question)
    await session.flush()  # get question.id

    if choices:
        for choice in choices:
            session.add(
                Choice(
                    question_id=question.id,
                    value=choice["value"],
                    ordinal=choice.get("ordinal"),
                    is_correct=choice.get("is_correct", False),
                )
            )

    # Keep transaction control at service/router level; repository only flushes.
    await session.flush()
    await session.refresh(question)
    return question


async def get_question_with_choices(session, question_id: int):
    stmt = select(Question).options(selectinload(Question.choices)).where(Question.id == question_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def list_questions_for_test(session, test_id: int, limit: int = 100, offset: int = 0):
    stmt = (
        select(Question)
        .options(selectinload(Question.choices))
        .where(Question.test_id == test_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def delete_questions_for_test(session, test_id: int):
    await session.execute(delete(Question).where(Question.test_id == test_id))
    await session.flush()


async def update_question(
    session,
    question_id: int,
    *,
    text: str | None = None,
    points: float | None = None,
    is_open_answer: bool | None = None,
    material_urls: list[str] | None = None,
):
    question = await get_question_with_choices(session, question_id)
    if question is None:
        return None

    if text is not None:
        question.text = text
    if points is not None:
        question.points = points
    if is_open_answer is not None:
        question.is_open_answer = is_open_answer
    if material_urls is not None:
        question.material_urls = material_urls

    await session.flush()
    await session.refresh(question)
    return question


async def delete_question(session, question_id: int):
    await session.execute(delete(Question).where(Question.id == question_id))
    await session.flush()

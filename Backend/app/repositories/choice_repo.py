from sqlalchemy import select, delete
from app.models.choice import Choice

async def list_choices_for_question(session, question_id: int):
    q = select(Choice).where(Choice.question_id == question_id).order_by(Choice.ordinal)
    res = await session.execute(q)
    return res.scalars().all()

async def create_choice(session, question_id: int, value: str, ordinal: int | None = None, is_correct: bool = False):
    ch = Choice(question_id=question_id, value=value, ordinal=ordinal, is_correct=is_correct)
    session.add(ch)
    await session.flush()
    await session.refresh(ch)
    return ch

async def update_choice(
    session,
    choice_id: int,
    *,
    value: str | None = None,
    ordinal: int | None = None,
    is_correct: bool | None = None,
):
    choice = await session.get(Choice, choice_id)
    if choice is None:
        return None

    if value is not None:
        choice.value = value
    if ordinal is not None:
        choice.ordinal = ordinal
    if is_correct is not None:
        choice.is_correct = is_correct

    await session.flush()
    await session.refresh(choice)
    return choice

async def delete_choice(session, choice_id: int):
    await session.execute(delete(Choice).where(Choice.id == choice_id))
    await session.flush()
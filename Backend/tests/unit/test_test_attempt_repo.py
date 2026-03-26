import pytest

pytestmark = pytest.mark.asyncio

from app.models.answer import Answer
from app.models.question import Question
from app.models.test_ import Test as TestModel
from app.models.user import User
from app.repositories.test_attempt_repo import create_attempt, complete_attempt


@pytest.mark.asyncio
async def test_complete_attempt_aggregates_scores(session):
    user = User(username="attempt_user", password_hash="x")
    test = TestModel(title="attempted test")
    session.add_all([user, test])
    await session.flush()
    await session.refresh(user)
    await session.refresh(test)

    q1 = Question(test_id=test.id, text="Q1", points=2.5, is_open_answer=False)
    q2 = Question(test_id=test.id, text="Q2", points=4.0, is_open_answer=True)
    session.add_all([q1, q2])
    await session.flush()
    await session.refresh(q1)
    await session.refresh(q2)

    attempt = await create_attempt(session, user.id, test.id)
    session.add_all(
        [
            Answer(
                user_id=user.id,
                test_id=test.id,
                attempt_id=attempt.id,
                question_id=q1.id,
                answer_payload="1",
                score=2.5,
            ),
            Answer(
                user_id=user.id,
                test_id=test.id,
                attempt_id=attempt.id,
                question_id=q2.id,
                answer_payload="essay",
                score=3.0,
            ),
        ]
    )
    await session.flush()

    completed = await complete_attempt(session, attempt)

    assert completed.status == "completed"
    assert completed.score == pytest.approx(5.5)
    assert completed.max_score == pytest.approx(6.5)
    assert completed.completed_at is not None

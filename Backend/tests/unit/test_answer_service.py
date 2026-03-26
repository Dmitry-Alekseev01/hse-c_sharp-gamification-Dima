import pytest
pytestmark = pytest.mark.asyncio

from app.repositories import analytics_repo
from app.models.user import User
from app.models.test_ import Test as TestModel
from app.models.question import Question
from app.models.choice import Choice
from app.models.answer import Answer
from app.repositories.test_attempt_repo import create_attempt, complete_attempt
from app.services.answer_service import submit_answer, manual_grade_open_answer

@pytest.mark.asyncio
async def test_submit_mcq_full_flow(db):
    """
    Full flow using the test 'db' session fixture (isolated per-test).
    Creates user/test/question/choice, submits answer via service, asserts grading and analytics update.
    """
    # create user
    user = User(username="int_user", password_hash="x")
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # create test
    test = TestModel(title="integration test")
    db.add(test)
    await db.flush()
    await db.refresh(test)

    # create question
    q = Question(test_id=test.id, text="Integr Q", points=4.0, is_open_answer=False)
    db.add(q)
    await db.flush()
    await db.refresh(q)

    # create correct choice
    c = Choice(question_id=q.id, value="OK", ordinal=1, is_correct=True)
    db.add(c)
    await db.flush()
    await db.refresh(c)

    # submit answer (MCQ) — use service
    ans = await submit_answer(db, user_id=user.id, test_id=test.id, question_id=q.id, payload=str(c.id))

    # reload answer from DB
    db_ans = await db.get(Answer, ans.id)
    assert db_ans is not None
    assert db_ans.score == pytest.approx(4.0)

    # analytics
    analytics = await analytics_repo.get_user_analytics(db, user.id)
    assert analytics is not None
    assert analytics.total_points == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_manual_grade_open_answer_updates_score_and_analytics(db):
    teacher = User(username="teacher_1", password_hash="x", role="teacher")
    student = User(username="student_1", password_hash="x", role="user")
    db.add_all([teacher, student])
    await db.flush()

    test = TestModel(title="open grading test")
    db.add(test)
    await db.flush()

    question = Question(test_id=test.id, text="Explain polymorphism", points=7.0, is_open_answer=True)
    db.add(question)
    await db.flush()

    answer = Answer(
        user_id=student.id,
        test_id=test.id,
        question_id=question.id,
        answer_payload="Some free-form answer",
    )
    db.add(answer)
    await db.flush()
    await db.refresh(answer)

    graded = await manual_grade_open_answer(db, answer.id, teacher.id, 5.5)

    assert graded.score == pytest.approx(5.5)
    assert graded.graded_by == teacher.id
    assert graded.graded_at is not None

    analytics = await analytics_repo.get_user_analytics(db, student.id)
    assert analytics is not None
    assert analytics.total_points == pytest.approx(5.5)


@pytest.mark.asyncio
async def test_manual_grade_open_answer_rejects_non_open_question(db):
    teacher = User(username="teacher_2", password_hash="x", role="teacher")
    student = User(username="student_2", password_hash="x", role="user")
    db.add_all([teacher, student])
    await db.flush()

    test = TestModel(title="mcq grading test")
    db.add(test)
    await db.flush()

    question = Question(test_id=test.id, text="2+2?", points=3.0, is_open_answer=False)
    db.add(question)
    await db.flush()

    answer = Answer(
        user_id=student.id,
        test_id=test.id,
        question_id=question.id,
        answer_payload="4",
    )
    db.add(answer)
    await db.flush()

    with pytest.raises(ValueError, match="open-answer questions"):
        await manual_grade_open_answer(db, answer.id, teacher.id, 2.0)


@pytest.mark.asyncio
async def test_manual_grade_open_answer_refreshes_completed_attempt_totals(db):
    teacher = User(username="teacher_3", password_hash="x", role="teacher")
    student = User(username="student_3", password_hash="x", role="user")
    db.add_all([teacher, student])
    await db.flush()

    test = TestModel(title="completed attempt refresh")
    db.add(test)
    await db.flush()

    question = Question(test_id=test.id, text="Explain interfaces", points=6.0, is_open_answer=True)
    db.add(question)
    await db.flush()

    attempt = await create_attempt(db, student.id, test.id)
    answer = Answer(
        user_id=student.id,
        test_id=test.id,
        attempt_id=attempt.id,
        question_id=question.id,
        answer_payload="draft answer",
    )
    db.add(answer)
    await db.flush()
    await complete_attempt(db, attempt)

    refreshed = await manual_grade_open_answer(db, answer.id, teacher.id, 4.5)

    assert refreshed.score == pytest.approx(4.5)
    completed_attempt = await db.get(type(attempt), attempt.id)
    assert completed_attempt is not None
    assert completed_attempt.score == pytest.approx(4.5)
    assert completed_attempt.max_score == pytest.approx(6.0)

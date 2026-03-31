import pytest
pytestmark = pytest.mark.asyncio

from app.repositories import analytics_repo
from app.repositories import question_repo
from app.models.user import User
from app.models.test_ import Test as TestModel
from app.models.question import Question
from app.models.choice import Choice
from app.models.answer import Answer
from app.repositories.test_attempt_repo import create_attempt, complete_attempt
from app.schemas.question import QuestionRead
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


@pytest.mark.asyncio
async def test_submit_answer_rejects_choice_from_another_question(db):
    user = User(username="choice_validation_user", password_hash="x")
    test = TestModel(title="choice validation test")
    db.add_all([user, test])
    await db.flush()

    q1 = Question(test_id=test.id, text="Q1", points=2.0, is_open_answer=False)
    q2 = Question(test_id=test.id, text="Q2", points=2.0, is_open_answer=False)
    db.add_all([q1, q2])
    await db.flush()

    foreign_choice = Choice(question_id=q2.id, value="wrong scope", ordinal=1, is_correct=True)
    db.add(foreign_choice)
    await db.flush()

    with pytest.raises(ValueError, match="does not belong to the specified question"):
        await submit_answer(db, user_id=user.id, test_id=test.id, question_id=q1.id, payload=str(foreign_choice.id))


@pytest.mark.asyncio
async def test_submit_answer_replaces_existing_attempt_answer_without_double_counting(db):
    user = User(username="upsert_answer_user", password_hash="x")
    test = TestModel(title="upsert test")
    db.add_all([user, test])
    await db.flush()

    question = Question(test_id=test.id, text="Pick the right answer", points=4.0, is_open_answer=False)
    db.add(question)
    await db.flush()

    wrong_choice = Choice(question_id=question.id, value="wrong", ordinal=1, is_correct=False)
    right_choice = Choice(question_id=question.id, value="right", ordinal=2, is_correct=True)
    db.add_all([wrong_choice, right_choice])
    await db.flush()

    attempt = await create_attempt(db, user.id, test.id)

    first = await submit_answer(
        db,
        user_id=user.id,
        test_id=test.id,
        question_id=question.id,
        payload=str(right_choice.id),
        attempt_id=attempt.id,
    )
    second = await submit_answer(
        db,
        user_id=user.id,
        test_id=test.id,
        question_id=question.id,
        payload=str(wrong_choice.id),
        attempt_id=attempt.id,
    )

    analytics = await analytics_repo.get_user_analytics(db, user.id)
    refreshed_attempt = await db.get(type(attempt), attempt.id)

    assert first.id == second.id
    assert second.score == pytest.approx(0.0)
    assert analytics is not None
    assert analytics.total_points == pytest.approx(0.0)
    assert refreshed_attempt is not None
    assert refreshed_attempt.score == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_public_question_schema_hides_correct_answers(db):
    test = TestModel(title="public schema test")
    db.add(test)
    await db.flush()

    question = Question(test_id=test.id, text="Secure question", points=1.0, is_open_answer=False)
    db.add(question)
    await db.flush()

    choice = Choice(question_id=question.id, value="secret", ordinal=1, is_correct=True)
    db.add(choice)
    await db.flush()

    loaded_question = await question_repo.get_question_with_choices(db, question.id)
    payload = QuestionRead.model_validate(loaded_question).model_dump()

    assert payload["choices"]
    assert "is_correct" not in payload["choices"][0]

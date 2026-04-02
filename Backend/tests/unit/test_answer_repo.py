# tests/unit/test_answer_repo.py
import pytest
pytestmark = pytest.mark.asyncio
from app.repositories.answer_repo import record_answer, grade_mcq_answer, get_pending_open_answers
from app.models.user import User
from app.models.test_ import Test as TestModel
from app.models.question import Question
from app.models.choice import Choice
from app.models.answer import Answer

@pytest.mark.asyncio
async def test_record_and_grade_mcq_correct(session):
    # create user, test, question, choice
    u = User(username="u1", password_hash="x")
    session.add(u)
    await session.flush()
    await session.refresh(u)

    t = TestModel(title="t1")
    session.add(t)
    await session.flush()
    await session.refresh(t)

    q = Question(test_id=t.id, text="2+2?", points=5.0, is_open_answer=False)
    session.add(q)
    await session.flush()
    await session.refresh(q)

    # correct choice
    c_wrong = Choice(question_id=q.id, value="3", ordinal=1, is_correct=False)
    c_right = Choice(question_id=q.id, value="4", ordinal=2, is_correct=True)
    session.add_all([c_wrong, c_right])
    await session.flush()
    await session.refresh(c_right)

    # record answer using record_answer (payload is stringified choice id)
    ans = await record_answer(session, user_id=u.id, test_id=t.id, question_id=q.id, payload=str(c_right.id))
    assert isinstance(ans, Answer)
    assert ans.answer_payload == str(c_right.id)

    # grade it
    graded = await grade_mcq_answer(session, ans.id)
    assert graded is not None
    # correct -> full points
    assert graded.score == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_grade_mcq_bad_payload_no_crash(session):
    # create minimal entities
    u = User(username="u2", password_hash="x"); session.add(u)
    t = TestModel(title="t2"); session.add(t)
    await session.flush()
    await session.refresh(u); await session.refresh(t)
    q = Question(test_id=t.id, text="free", points=2.0, is_open_answer=False)
    session.add(q); await session.flush(); await session.refresh(q)

    # record answer with non-int payload
    ans = await record_answer(session, user_id=u.id, test_id=t.id, question_id=q.id, payload="not-an-int")
    # attempt grading - should not raise and should leave score None
    graded = await grade_mcq_answer(session, ans.id)
    assert graded is not None
    assert graded.score is None


@pytest.mark.asyncio
async def test_get_pending_open_answers_returns_only_ungraded_open_answers(session):
    teacher = User(username="teacher_pending", password_hash="x", role="teacher")
    student = User(username="student_pending", password_hash="x", role="user")
    session.add_all([teacher, student])
    await session.flush()
    await session.refresh(student)

    test = TestModel(title="pending-open")
    session.add(test)
    await session.flush()
    await session.refresh(test)

    open_question = Question(test_id=test.id, text="Explain abstraction", points=5.0, is_open_answer=True)
    mcq_question = Question(test_id=test.id, text="2+2?", points=1.0, is_open_answer=False)
    session.add_all([open_question, mcq_question])
    await session.flush()
    await session.refresh(open_question)
    await session.refresh(mcq_question)

    pending_answer = Answer(
        user_id=student.id,
        test_id=test.id,
        question_id=open_question.id,
        answer_payload="free text",
        score=None,
    )
    graded_open_answer = Answer(
        user_id=student.id,
        test_id=test.id,
        question_id=open_question.id,
        answer_payload="already checked",
        score=4.0,
        graded_by=teacher.id,
    )
    mcq_answer = Answer(
        user_id=student.id,
        test_id=test.id,
        question_id=mcq_question.id,
        answer_payload="1",
        score=None,
    )
    session.add_all([pending_answer, graded_open_answer, mcq_answer])
    await session.flush()

    pending = await get_pending_open_answers(session)

    assert [answer.id for answer in pending] == [pending_answer.id]


@pytest.mark.asyncio
async def test_get_pending_open_answers_can_filter_by_test_author(session):
    teacher_a = User(username="pending_teacher_a", password_hash="x", role="teacher")
    teacher_b = User(username="pending_teacher_b", password_hash="x", role="teacher")
    student = User(username="pending_student", password_hash="x", role="user")
    session.add_all([teacher_a, teacher_b, student])
    await session.flush()

    test_a = TestModel(title="Teacher A test", author_id=teacher_a.id)
    test_b = TestModel(title="Teacher B test", author_id=teacher_b.id)
    session.add_all([test_a, test_b])
    await session.flush()

    question_a = Question(test_id=test_a.id, text="Open A", points=5.0, is_open_answer=True)
    question_b = Question(test_id=test_b.id, text="Open B", points=5.0, is_open_answer=True)
    session.add_all([question_a, question_b])
    await session.flush()

    answer_a = Answer(user_id=student.id, test_id=test_a.id, question_id=question_a.id, answer_payload="A")
    answer_b = Answer(user_id=student.id, test_id=test_b.id, question_id=question_b.id, answer_payload="B")
    session.add_all([answer_a, answer_b])
    await session.flush()

    pending = await get_pending_open_answers(session, author_id=teacher_a.id)

    assert [answer.id for answer in pending] == [answer_a.id]

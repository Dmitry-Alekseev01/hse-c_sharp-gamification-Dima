import pytest
from fastapi import HTTPException
from datetime import UTC, datetime, timedelta

pytestmark = pytest.mark.asyncio

from app.api.v1 import access
from app.models.answer import Answer
from app.models.choice import Choice
from app.models.level import Level
from app.models.material import Material
from app.models.question import Question
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.models.user import User
from app.repositories import analytics_repo, group_repo


@pytest.mark.asyncio
async def test_locked_test_and_material_depend_on_required_level_points(db):
    user = User(username="unlock_user", password_hash="x", role="user")
    level = Level(name="Level 2", required_points=50)
    source_test = Test(title="Scoring source", published=True, max_score=100, max_attempts=3)
    db.add_all([user, level, source_test])
    await db.flush()

    test = Test(title="Locked test", published=True, required_level_id=level.id)
    material = Material(title="Locked material", required_level_id=level.id)
    db.add_all([test, material])
    await db.flush()
    await db.refresh(test)
    await db.refresh(material)

    initial_points = await analytics_repo.get_access_points_for_user(db, user.id)
    assert await access.is_unlocked_test(db, user, test, total_points=initial_points) is False
    assert await access.is_unlocked_material(db, user, material, total_points=initial_points) is False

    first_completed_attempt = TestAttempt(
        user_id=user.id,
        test_id=source_test.id,
        status="completed",
        score=60.0,
        max_score=100.0,
        submitted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
        completed_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
    )
    db.add(first_completed_attempt)
    await db.flush()

    test = await access.get_test_or_404(db, test.id)
    material = await access.get_material_or_404(db, material.id)

    unlocked_points = await analytics_repo.get_access_points_for_user(db, user.id)
    assert await access.is_unlocked_test(db, user, test, total_points=unlocked_points) is True
    assert await access.is_unlocked_material(db, user, material, total_points=unlocked_points) is True

    second_completed_attempt = TestAttempt(
        user_id=user.id,
        test_id=source_test.id,
        status="completed",
        score=10.0,
        max_score=100.0,
        submitted_at=datetime.now(UTC).replace(tzinfo=None),
        completed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(second_completed_attempt)
    await db.flush()

    relocked_points = await analytics_repo.get_access_points_for_user(db, user.id)
    assert await access.is_unlocked_test(db, user, test, total_points=relocked_points) is False
    assert await access.is_unlocked_material(db, user, material, total_points=relocked_points) is False


@pytest.mark.asyncio
async def test_locked_test_access_uses_legacy_answer_scores_without_attempts(db):
    user = User(username="legacy_unlock_user", password_hash="x", role="user")
    level = Level(name="Legacy level", required_points=20)
    source_test = Test(title="Legacy source", published=True, max_score=20, max_attempts=1)
    db.add_all([user, level, source_test])
    await db.flush()

    question = Question(test_id=source_test.id, text="Legacy q", points=20.0, is_open_answer=False)
    db.add(question)
    await db.flush()

    choice = Choice(question_id=question.id, value="A", ordinal=1, is_correct=True)
    db.add(choice)
    await db.flush()

    locked_test = Test(title="Legacy locked test", published=True, required_level_id=level.id)
    db.add(locked_test)
    await db.flush()

    # Backward-compatible legacy dataset: answers linked directly to test, no attempt_id.
    legacy_answer = Answer(
        user_id=user.id,
        test_id=source_test.id,
        question_id=question.id,
        answer_payload=str(choice.id),
        score=20.0,
        attempt_id=None,
    )
    db.add(legacy_answer)
    await db.flush()

    legacy_points = await analytics_repo.get_access_points_for_user(db, user.id)
    assert await access.is_unlocked_test(db, user, locked_test, total_points=legacy_points) is True


@pytest.mark.asyncio
async def test_ensure_level_exists_or_400_rejects_unknown_level(db):
    with pytest.raises(HTTPException) as exc_info:
        await access.ensure_level_exists_or_400(db, 999999)

    assert exc_info.value.status_code == 400
    assert "required_level_id" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_ensure_teacher_or_admin_can_access_user_allows_admin(db):
    admin = User(username="access_admin_case", password_hash="x", role="admin")
    student = User(username="access_student_case", password_hash="x", role="user")
    db.add_all([admin, student])
    await db.flush()

    await access.ensure_teacher_or_admin_can_access_user(db, admin, student.id)


@pytest.mark.asyncio
async def test_ensure_teacher_or_admin_can_access_user_restricts_teacher_to_managed_students(db):
    teacher = User(username="access_teacher_case", password_hash="x", role="teacher")
    managed_student = User(username="managed_student_case", password_hash="x", role="user")
    unmanaged_student = User(username="unmanaged_student_case", password_hash="x", role="user")
    db.add_all([teacher, managed_student, unmanaged_student])
    await db.flush()

    group = await group_repo.create_group(db, "access-policy-group", teacher.id)
    await group_repo.add_user_to_group(db, group, managed_student.id)

    await access.ensure_teacher_or_admin_can_access_user(db, teacher, teacher.id)
    await access.ensure_teacher_or_admin_can_access_user(db, teacher, managed_student.id)

    with pytest.raises(HTTPException) as exc_info:
        await access.ensure_teacher_or_admin_can_access_user(db, teacher, unmanaged_student.id)
    assert exc_info.value.status_code == 403

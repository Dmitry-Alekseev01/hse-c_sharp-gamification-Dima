import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio

from app.api.v1 import access
from app.models.level import Level
from app.models.material import Material
from app.models.test_ import Test
from app.models.user import User
from app.repositories import analytics_repo, group_repo


@pytest.mark.asyncio
async def test_locked_test_and_material_depend_on_required_level_points(db):
    user = User(username="unlock_user", password_hash="x", role="user")
    level = Level(name="Level 2", required_points=50)
    db.add_all([user, level])
    await db.flush()

    test = Test(title="Locked test", published=True, required_level_id=level.id)
    material = Material(title="Locked material", required_level_id=level.id)
    db.add_all([test, material])
    await db.flush()
    await db.refresh(test)
    await db.refresh(material)

    assert await access.is_unlocked_test(db, user, test) is False
    assert await access.is_unlocked_material(db, user, material) is False

    await analytics_repo.create_or_update_analytics(db, user.id, points_delta=60.0, mark_active=True)
    test = await access.get_test_or_404(db, test.id)
    material = await access.get_material_or_404(db, material.id)

    assert await access.is_unlocked_test(db, user, test) is True
    assert await access.is_unlocked_material(db, user, material) is True


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

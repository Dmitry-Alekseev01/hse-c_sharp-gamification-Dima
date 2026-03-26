import pytest

pytestmark = pytest.mark.asyncio

from app.models.user import User
from app.repositories import group_repo


@pytest.mark.asyncio
async def test_create_group_and_manage_members(db):
    teacher = User(username="group_teacher", password_hash="x", role="teacher")
    student = User(username="group_student", password_hash="x", role="user")
    db.add_all([teacher, student])
    await db.flush()
    await db.refresh(teacher)
    await db.refresh(student)

    group = await group_repo.create_group(db, "BPI-101", teacher.id)
    await group_repo.add_user_to_group(db, group, student.id)
    group_id = group.id
    student_id = student.id

    db.expire_all()
    loaded = await group_repo.get_group(db, group_id)
    assert loaded is not None
    assert loaded.name == "BPI-101"
    assert [membership.user_id for membership in loaded.memberships] == [student_id]

    removed = await group_repo.remove_user_from_group(db, loaded, student.id)
    assert removed is True

    db.expire_all()
    loaded_again = await group_repo.get_group(db, group_id)
    assert loaded_again is not None
    assert loaded_again.memberships == []

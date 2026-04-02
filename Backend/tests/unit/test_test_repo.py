import pytest

pytestmark = pytest.mark.asyncio

from app.models.user import User
from app.repositories import test_repo


@pytest.mark.asyncio
async def test_list_tests_can_filter_by_author(db):
    teacher_a = User(username="teacher_a", password_hash="x", role="teacher")
    teacher_b = User(username="teacher_b", password_hash="x", role="teacher")
    db.add_all([teacher_a, teacher_b])
    await db.flush()

    await test_repo.create_test(db, title="Owned by A", author_id=teacher_a.id)
    await test_repo.create_test(db, title="Owned by B", author_id=teacher_b.id)

    teacher_a_tests = await test_repo.list_tests(db, published_only=False, author_id=teacher_a.id)

    assert len(teacher_a_tests) == 1
    assert teacher_a_tests[0].title == "Owned by A"
    assert teacher_a_tests[0].author_id == teacher_a.id

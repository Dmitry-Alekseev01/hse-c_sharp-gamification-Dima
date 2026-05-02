import pytest

pytestmark = pytest.mark.asyncio

from app.models.user import User
from app.models.material import Material
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


@pytest.mark.asyncio
async def test_create_test_sets_default_max_attempts(db):
    test = await test_repo.create_test(db, title="Default attempts")

    assert test.max_attempts == 1


@pytest.mark.asyncio
async def test_create_test_persists_material_links_from_material_ids(db):
    material_a = Material(title="A", material_type="lesson", status="published")
    material_b = Material(title="B", material_type="lesson", status="published")
    db.add_all([material_a, material_b])
    await db.flush()

    test = await test_repo.create_test(
        db,
        title="T with links",
        material_ids=[material_b.id, material_a.id],
    )

    assert set(test.material_ids) == {material_a.id, material_b.id}


@pytest.mark.asyncio
async def test_update_test_replaces_material_links_from_material_ids(db):
    material_a = Material(title="A2", material_type="lesson", status="published")
    material_b = Material(title="B2", material_type="lesson", status="published")
    db.add_all([material_a, material_b])
    await db.flush()

    test = await test_repo.create_test(db, title="Sync test", material_ids=[material_a.id])
    assert test.material_ids == [material_a.id]

    updated = await test_repo.update_test(db, test.id, material_ids=[material_b.id])
    assert updated is not None
    assert updated.material_ids == [material_b.id]


@pytest.mark.asyncio
async def test_update_test_updates_max_attempts(db):
    test = await test_repo.create_test(db, title="Attempts update", max_attempts=1)

    updated = await test_repo.update_test(db, test.id, max_attempts=3)

    assert updated is not None
    assert updated.max_attempts == 3

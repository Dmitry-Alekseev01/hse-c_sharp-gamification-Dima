import pytest

pytestmark = pytest.mark.asyncio

from app.services import user_service


@pytest.mark.asyncio
async def test_register_user_can_assign_role_when_used_by_admin_flow(db):
    user = await user_service.register_user(
        db,
        username="teacher_seed",
        password="secret",
        full_name="Teacher Seed",
        role="teacher",
    )

    assert user.role == "teacher"

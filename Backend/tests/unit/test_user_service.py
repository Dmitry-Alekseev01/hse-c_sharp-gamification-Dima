import pytest

pytestmark = pytest.mark.asyncio

from app.core.security import verify_password
from app.services import user_service


@pytest.mark.asyncio
async def test_register_user_can_assign_role_when_used_by_admin_flow(db):
    user = await user_service.register_user(
        db,
        username="teacher_seed",
        password="TeacherSeed1!",
        full_name="Teacher Seed",
        role="teacher",
    )

    assert user.role == "teacher"


@pytest.mark.asyncio
async def test_change_user_password_updates_hash_and_verification(db):
    user = await user_service.register_user(
        db,
        username="password_change_user",
        password="Old_password_123!",
        full_name="Password User",
        role="user",
    )

    updated = await user_service.change_user_password(
        db,
        user.id,
        current_password="Old_password_123!",
        new_password="New_password_456!",
    )

    assert verify_password("New_password_456!", updated.password_hash)
    assert not verify_password("Old_password_123!", updated.password_hash)


@pytest.mark.asyncio
async def test_change_user_password_rejects_invalid_current_password(db):
    user = await user_service.register_user(
        db,
        username="password_change_user_invalid",
        password="Old_password_123!",
        full_name="Password User Invalid",
        role="user",
    )

    with pytest.raises(ValueError, match="Current password is incorrect"):
        await user_service.change_user_password(
            db,
            user.id,
            current_password="wrong_password",
            new_password="New_password_456!",
        )


@pytest.mark.asyncio
async def test_change_user_password_rejects_short_or_same_password(db):
    user = await user_service.register_user(
        db,
        username="password_change_user_short",
        password="Old_password_123!",
        full_name="Password User Short",
        role="user",
    )

    with pytest.raises(ValueError, match="differ"):
        await user_service.change_user_password(
            db,
            user.id,
            current_password="Old_password_123!",
            new_password="Old_password_123!",
        )

    with pytest.raises(ValueError, match="at least"):
        await user_service.change_user_password(
            db,
            user.id,
            current_password="Old_password_123!",
            new_password="short",
        )


@pytest.mark.asyncio
async def test_change_user_password_rejects_policy_violations(db):
    user = await user_service.register_user(
        db,
        username="password_change_policy",
        password="Old_password_123!",
        full_name="Password User Policy",
        role="user",
    )

    with pytest.raises(ValueError, match="uppercase"):
        await user_service.change_user_password(
            db,
            user.id,
            current_password="Old_password_123!",
            new_password="new_password_456!",
        )

    with pytest.raises(ValueError, match="special"):
        await user_service.change_user_password(
            db,
            user.id,
            current_password="Old_password_123!",
            new_password="Newpassword4567",
        )

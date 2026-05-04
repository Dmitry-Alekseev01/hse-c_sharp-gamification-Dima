from types import SimpleNamespace

import pytest

from app.admin.views import (
    AchievementDefinitionAdminView,
    ChallengeAdminView,
    GroupMembershipAdminView,
    MaterialAdminView,
    MaterialAttachmentAdminView,
    MaterialBlockAdminView,
    RewardDefinitionAdminView,
    SeasonAdminView,
    StudyGroupAdminView,
    TestAdminView as _TestAdminView,
    UnlockRuleAdminView,
    UserReadOnlyView,
    get_admin_views,
)
from app.models.challenge import Challenge
from app.models.achievement_definition import AchievementDefinition
from app.models.group import GroupMembership, StudyGroup
from app.models.material import Material
from app.models.material_attachment import MaterialAttachment
from app.models.material_block import MaterialBlock
from app.models.reward_definition import RewardDefinition
from app.models.season import Season
from app.models.test_ import Test
from app.models.unlock_rule import UnlockRule
from app.models.user import User

pytestmark = pytest.mark.asyncio


class _DummyRequest:
    def __init__(self, *, role: str, user_id: int = 1):
        self.session = {
            "admin_role": role,
            "admin_user_id": user_id,
            "admin_username": f"{role}@example.com",
        }
        self.state = SimpleNamespace(admin_user=SimpleNamespace(id=user_id, username=f"{role}@example.com"))


async def test_user_view_not_accessible_for_teacher():
    view = UserReadOnlyView(User)
    request = _DummyRequest(role="teacher", user_id=7)

    assert view.is_accessible(request) is False


async def test_material_view_teacher_can_write_and_is_owner_scoped():
    view = MaterialAdminView(Material)
    request = _DummyRequest(role="teacher", user_id=7)

    assert view.is_accessible(request) is True
    assert view.can_create(request) is True
    assert view.can_edit(request) is True
    assert view.can_delete(request) is True

    stmt = view.get_list_query(request)
    assert "materials.author_id" in str(stmt)

    data = {"title": "M1", "material_type": "lesson", "status": "draft"}
    await view.before_create(request, data, None)
    assert data["author_id"] == 7


async def test_test_view_teacher_before_create_sets_author():
    view = _TestAdminView(Test)
    request = _DummyRequest(role="teacher", user_id=11)

    data = {"title": "T1", "published": False}
    await view.before_create(request, data, None)
    assert data["author_id"] == 11


async def test_material_and_test_views_use_required_level_relation_field():
    material_view = MaterialAdminView(Material)
    test_view = _TestAdminView(Test)

    material_field_names = [field.name for field in material_view.fields]
    test_field_names = [field.name for field in test_view.fields]

    assert "required_level" in material_field_names
    assert "required_level_id" not in material_field_names
    assert "required_level" in test_field_names
    assert "required_level_id" not in test_field_names


async def test_group_views_teacher_access_enabled():
    teacher_request = _DummyRequest(role="teacher", user_id=3)
    group_view = StudyGroupAdminView(StudyGroup)
    membership_view = GroupMembershipAdminView(GroupMembership)

    assert group_view.is_accessible(teacher_request) is True
    assert group_view.can_create(teacher_request) is True
    assert membership_view.is_accessible(teacher_request) is True

    group_stmt = group_view.get_list_query(teacher_request)
    membership_stmt = membership_view.get_list_query(teacher_request)
    assert "study_groups.teacher_id" in str(group_stmt)
    assert "study_groups.teacher_id" in str(membership_stmt)


async def test_admin_views_contains_material_block_and_attachment_views():
    views = get_admin_views()
    model_names = {getattr(view.model, "__name__", "") for view in views}

    assert MaterialBlock.__name__ in model_names
    assert MaterialAttachment.__name__ in model_names
    assert AchievementDefinition.__name__ in model_names

    block_view = next(view for view in views if getattr(view.model, "__name__", "") == MaterialBlock.__name__)
    attachment_view = next(
        view for view in views if getattr(view.model, "__name__", "") == MaterialAttachment.__name__
    )

    teacher_request = _DummyRequest(role="teacher", user_id=4)
    assert isinstance(block_view, MaterialBlockAdminView)
    assert isinstance(attachment_view, MaterialAttachmentAdminView)
    assert block_view.is_accessible(teacher_request) is True
    assert attachment_view.is_accessible(teacher_request) is True


async def test_config_views_are_admin_only():
    teacher_request = _DummyRequest(role="teacher", user_id=4)
    admin_request = _DummyRequest(role="admin", user_id=1)

    reward_view = RewardDefinitionAdminView(RewardDefinition)
    unlock_view = UnlockRuleAdminView(UnlockRule)
    challenge_view = ChallengeAdminView(Challenge)
    season_view = SeasonAdminView(Season)
    achievement_view = AchievementDefinitionAdminView(AchievementDefinition)

    assert reward_view.is_accessible(admin_request) is True
    assert unlock_view.is_accessible(admin_request) is True
    assert challenge_view.is_accessible(admin_request) is True
    assert season_view.is_accessible(admin_request) is True
    assert achievement_view.is_accessible(admin_request) is True

    assert reward_view.is_accessible(teacher_request) is False
    assert unlock_view.is_accessible(teacher_request) is False
    assert challenge_view.is_accessible(teacher_request) is False
    assert season_view.is_accessible(teacher_request) is False
    assert achievement_view.is_accessible(teacher_request) is False

from types import SimpleNamespace

import pytest
from starlette_admin.exceptions import FormValidationError

from app.admin.views import (
    AchievementDefinitionAdminView,
    ChallengeAdminView,
    ChoiceAdminView,
    GroupMembershipAdminView,
    MaterialAdminView,
    MaterialAttachmentAdminView,
    MaterialBlockAdminView,
    QuestionAdminView,
    RewardDefinitionAdminView,
    SeasonAdminView,
    TestAdminView as _TestAdminView,
    UnlockRuleAdminView,
)
from app.core.security import get_password_hash
from app.core.material_taxonomy import (
    AttachmentKind,
    MATERIAL_ATTACHMENT_KIND_VALUES,
    MATERIAL_BLOCK_TYPE_VALUES,
    MaterialBlockType,
)
from app.models.achievement_definition import AchievementDefinition
from app.models.challenge import Challenge
from app.models.choice import Choice
from app.models.group import GroupMembership
from app.models.material_attachment import MaterialAttachment
from app.models.material_block import MaterialBlock
from app.models.material import Material
from app.models.level import Level
from app.models.question import Question
from app.models.reward_definition import RewardDefinition
from app.models.season import Season
from app.models.test_ import Test
from app.models.unlock_rule import UnlockRule
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def test_question_admin_view_validate_rejects_missing_test_id():
    view = QuestionAdminView(Question)

    with pytest.raises(FormValidationError):
        await view.validate(None, {"text": "What is C#?", "points": 1.0})


async def test_question_admin_view_validate_accepts_valid_payload():
    view = QuestionAdminView(Question)

    await view.validate(None, {"test_id": 1, "text": "What is C#?", "points": 1.0})


async def test_question_admin_view_validate_accepts_relation_payload():
    view = QuestionAdminView(Question)

    await view.validate(None, {"test": {"id": 1}, "text": "What is CLR?", "points": 1.0})


async def test_choice_admin_view_validate_rejects_missing_question_id():
    view = ChoiceAdminView(Choice)

    with pytest.raises(FormValidationError):
        await view.validate(None, {"value": "CLR", "ordinal": 1, "is_correct": True})


async def test_choice_admin_view_validate_accepts_valid_payload():
    view = ChoiceAdminView(Choice)

    await view.validate(None, {"question_id": 1, "value": "CLR", "ordinal": 1, "is_correct": True})


async def test_choice_admin_view_validate_accepts_relation_payload():
    view = ChoiceAdminView(Choice)

    await view.validate(None, {"question": {"id": 1}, "value": "JIT", "ordinal": 2, "is_correct": False})


async def test_reward_definition_admin_view_validate_rejects_missing_code():
    view = RewardDefinitionAdminView(RewardDefinition)

    with pytest.raises(FormValidationError):
        await view.validate(None, {"title": "Badge", "reward_type": "badge"})


async def test_achievement_definition_admin_view_validate_rejects_invalid_criteria_type():
    view = AchievementDefinitionAdminView(AchievementDefinition)

    with pytest.raises(FormValidationError):
        await view.validate(
            None,
            {
                "code": "ach_invalid",
                "title": "Achievement",
                "description": "Desc",
                "criteria_type": "invalid",
                "threshold_value": 1,
                "is_active": True,
            },
        )


async def test_unlock_rule_admin_view_validate_rejects_invalid_source_type():
    view = UnlockRuleAdminView(UnlockRule)

    with pytest.raises(FormValidationError):
        await view.validate(
            None,
            {"reward_definition_id": 1, "source_type": "invalid", "source_code": "x", "min_level_required": 1},
        )


async def test_unlock_rule_admin_view_validate_accepts_relation_payload():
    view = UnlockRuleAdminView(UnlockRule)

    await view.validate(
        None,
        {"reward_definition": {"id": 1}, "source_type": "level", "source_code": "lvl_1", "min_level_required": 1},
    )


async def test_unlock_rule_admin_view_validate_rejects_non_existing_reward_definition(db):
    request = _DummyAdminRequest(db=db, user_id=1)
    view = UnlockRuleAdminView(UnlockRule)

    with pytest.raises(FormValidationError):
        await view.validate(
            request,
            {
                "reward_definition": {"id": 999999},
                "source_type": "level",
                "source_code": "lvl_1",
                "min_level_required": 1,
                "is_active": True,
            },
        )


async def test_challenge_admin_view_validate_rejects_invalid_event_type():
    view = ChallengeAdminView(Challenge)

    with pytest.raises(FormValidationError):
        await view.validate(
            None,
            {
                "code": "c1",
                "title": "Challenge",
                "period_type": "daily",
                "event_type": "invalid",
                "target_value": 1,
                "reward_points": 10,
            },
        )


async def test_challenge_admin_view_validate_rejects_non_existing_created_by(db):
    request = _DummyAdminRequest(db=db, user_id=1)
    view = ChallengeAdminView(Challenge)

    with pytest.raises(FormValidationError):
        await view.validate(
            request,
            {
                "code": "c_with_missing_creator",
                "title": "Challenge",
                "period_type": "daily",
                "event_type": "answer_submitted",
                "target_value": 1,
                "reward_points": 1.0,
                "created_by": 999999,
            },
        )


async def test_season_admin_view_validate_rejects_invalid_dates():
    view = SeasonAdminView(Season)

    with pytest.raises(FormValidationError):
        await view.validate(
            None,
            {
                "code": "s1",
                "title": "Season 1",
                "starts_at": "not-a-date",
                "ends_at": "also-not-a-date",
            },
        )


async def test_season_admin_view_validate_rejects_non_existing_created_by(db):
    request = _DummyAdminRequest(db=db, user_id=1)
    view = SeasonAdminView(Season)

    with pytest.raises(FormValidationError):
        await view.validate(
            request,
            {
                "code": "s1",
                "title": "Season 1",
                "starts_at": "2026-01-01T10:00:00",
                "ends_at": "2026-01-02T10:00:00",
                "created_by": 999999,
            },
        )


async def test_material_block_admin_view_validate_accepts_relation_payload():
    view = MaterialBlockAdminView(MaterialBlock)

    await view.validate(
        None,
        {
            "material": {"id": 1},
            "block_type": "text",
            "title": "Intro",
            "body": "Body",
            "order_index": 0,
        },
    )


async def test_material_block_admin_view_validate_accepts_all_schema_values():
    view = MaterialBlockAdminView(MaterialBlock)

    for block_type in MaterialBlockType:
        await view.validate(
            None,
            {
                "material": {"id": 1},
                "block_type": block_type.value,
                "title": "Block",
                "body": "Body",
                "order_index": 0,
            },
        )


async def test_material_block_admin_view_validate_rejects_outdated_admin_only_values():
    view = MaterialBlockAdminView(MaterialBlock)

    with pytest.raises(FormValidationError):
        await view.validate(
            None,
            {
                "material": {"id": 1},
                "block_type": "video",
                "title": "Legacy",
                "body": "Body",
                "order_index": 0,
            },
        )


async def test_material_attachment_admin_view_validate_accepts_relation_payload():
    view = MaterialAttachmentAdminView(MaterialAttachment)

    await view.validate(
        None,
        {
            "material": {"id": 1},
            "title": "Slides",
            "file_url": "https://example.com/slides.pdf",
            "file_kind": "pdf",
            "order_index": 1,
            "is_downloadable": True,
        },
    )


async def test_material_attachment_admin_view_validate_accepts_all_schema_values():
    view = MaterialAttachmentAdminView(MaterialAttachment)

    for attachment_kind in AttachmentKind:
        await view.validate(
            None,
            {
                "material": {"id": 1},
                "title": "Attachment",
                "file_url": "https://example.com/file.bin",
                "file_kind": attachment_kind.value,
                "order_index": 1,
                "is_downloadable": True,
            },
        )


async def test_material_attachment_admin_view_validate_rejects_outdated_admin_only_values():
    view = MaterialAttachmentAdminView(MaterialAttachment)

    with pytest.raises(FormValidationError):
        await view.validate(
            None,
            {
                "material": {"id": 1},
                "title": "Attachment",
                "file_url": "https://example.com/file.bin",
                "file_kind": "archive",
                "order_index": 1,
                "is_downloadable": True,
            },
        )


async def test_material_taxonomy_constants_match_schema_enums():
    assert MATERIAL_BLOCK_TYPE_VALUES == tuple(item.value for item in MaterialBlockType)
    assert MATERIAL_ATTACHMENT_KIND_VALUES == tuple(item.value for item in AttachmentKind)


async def test_group_membership_admin_view_validate_accepts_relation_payload():
    view = GroupMembershipAdminView(GroupMembership)

    await view.validate(None, {"group": {"id": 1}, "user": {"id": 2}})


class _DummyTeacherRequest:
    def __init__(self, *, db, teacher_id: int):
        self.session = {
            "admin_role": "teacher",
            "admin_user_id": teacher_id,
            "admin_username": f"teacher{teacher_id}@example.com",
        }
        self.state = SimpleNamespace(
            admin_user=SimpleNamespace(id=teacher_id, username=f"teacher{teacher_id}@example.com"),
            session=db,
        )


class _DummyAdminRequest:
    def __init__(self, *, db, user_id: int = 1):
        self.session = {
            "admin_role": "admin",
            "admin_user_id": user_id,
            "admin_username": f"admin{user_id}@example.com",
        }
        self.state = SimpleNamespace(
            admin_user=SimpleNamespace(id=user_id, username=f"admin{user_id}@example.com"),
            session=db,
        )


async def test_material_admin_view_validate_accepts_existing_required_level_relation(db):
    level = Level(name="Level A", required_points=10)
    db.add(level)
    await db.flush()

    request = _DummyAdminRequest(db=db, user_id=1)
    view = MaterialAdminView(Material)
    author = User(
        username="author_material_admin@example.com",
        full_name="Author Material Admin",
        password_hash=get_password_hash("secret123"),
        role="teacher",
    )
    db.add(author)
    await db.flush()
    await view.validate(
        request,
        {
            "title": "Material with level gate",
            "material_type": "lesson",
            "status": "draft",
            "required_level": {"id": level.id},
            "author_id": author.id,
        },
    )


async def test_material_admin_view_validate_rejects_non_existing_author(db):
    request = _DummyAdminRequest(db=db, user_id=1)
    view = MaterialAdminView(Material)

    with pytest.raises(FormValidationError):
        await view.validate(
            request,
            {
                "title": "Material with missing author",
                "material_type": "lesson",
                "status": "draft",
                "author_id": 999999,
            },
        )


async def test_test_admin_view_validate_rejects_non_existing_required_level(db):
    request = _DummyAdminRequest(db=db, user_id=1)
    view = _TestAdminView(Test)

    with pytest.raises(FormValidationError):
        await view.validate(
            request,
            {
                "title": "Test with broken level ref",
                "required_level": {"id": 999999},
            },
        )


async def test_test_admin_view_validate_rejects_non_existing_material_link(db):
    request = _DummyAdminRequest(db=db, user_id=1)
    view = _TestAdminView(Test)

    with pytest.raises(FormValidationError):
        await view.validate(
            request,
            {
                "title": "Test with missing material",
                "materials": [{"id": 999999}],
            },
        )


async def test_test_admin_view_validate_teacher_cannot_link_foreign_material(db):
    teacher_id = 100
    own_material = Material(
        title="Own material",
        material_type="lesson",
        status="draft",
        author_id=teacher_id,
    )
    foreign_material = Material(
        title="Foreign material",
        material_type="lesson",
        status="draft",
        author_id=999,
    )
    db.add_all([own_material, foreign_material])
    await db.flush()

    request = _DummyTeacherRequest(db=db, teacher_id=teacher_id)
    view = _TestAdminView(Test)

    await view.validate(
        request,
        {
            "title": "Teacher test",
            "materials": [{"id": own_material.id}],
        },
    )

    with pytest.raises(FormValidationError):
        await view.validate(
            request,
            {
                "title": "Teacher test with foreign material",
                "materials": [{"id": foreign_material.id}],
            },
        )

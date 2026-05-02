from types import SimpleNamespace

import pytest
from starlette_admin.exceptions import FormValidationError

from app.admin.views import (
    ChallengeAdminView,
    ChoiceAdminView,
    GroupMembershipAdminView,
    MaterialAttachmentAdminView,
    MaterialBlockAdminView,
    QuestionAdminView,
    RewardDefinitionAdminView,
    SeasonAdminView,
    TestAdminView as _TestAdminView,
    UnlockRuleAdminView,
)
from app.core.material_taxonomy import (
    AttachmentKind,
    MATERIAL_ATTACHMENT_KIND_VALUES,
    MATERIAL_BLOCK_TYPE_VALUES,
    MaterialBlockType,
)
from app.models.challenge import Challenge
from app.models.choice import Choice
from app.models.group import GroupMembership
from app.models.material_attachment import MaterialAttachment
from app.models.material_block import MaterialBlock
from app.models.material import Material
from app.models.question import Question
from app.models.reward_definition import RewardDefinition
from app.models.season import Season
from app.models.test_ import Test
from app.models.unlock_rule import UnlockRule

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

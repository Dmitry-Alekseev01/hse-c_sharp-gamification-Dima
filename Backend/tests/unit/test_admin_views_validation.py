from types import SimpleNamespace

import pytest
from starlette_admin.exceptions import FormValidationError

from app.admin.views import (
    AIGamificationJobReadOnlyView,
    AchievementDefinitionAdminView,
    ChallengeAdminView,
    ChoiceAdminView,
    GroupMembershipAdminView,
    LevelAdminView,
    MaterialAdminView,
    MaterialAttachmentAdminView,
    MaterialBlockAdminView,
    QuestionAdminView,
    RewardDefinitionAdminView,
    SeasonAdminView,
    TestAdminView as _TestAdminView,
    UnlockRuleAdminView,
)
from app.models.ai_gamification_job import AIGamificationJob
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


async def test_ai_job_admin_view_build_payload_accepts_placeholder_constraints_object():
    view = AIGamificationJobReadOnlyView(AIGamificationJob)

    payload = view._build_create_payload(
        {
            "source_type": "material",
            "source_id": 1,
            "language": "ru",
            "constraints_json": {"": ""},
        }
    )

    assert list(payload.constraints or []) == []


async def test_ai_job_admin_view_build_payload_accepts_items_wrapped_constraints():
    view = AIGamificationJobReadOnlyView(AIGamificationJob)

    payload = view._build_create_payload(
        {
            "source_type": "question",
            "source_id": 2,
            "language": "ru",
            "constraints_json": {"items": ["short cards", "anime tone"]},
        }
    )

    assert list(payload.constraints or []) == ["short cards", "anime tone"]


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


class _DummyActionRequest:
    def __init__(self, *, user_id: int, form_data: dict[str, str]):
        self.session = {
            "admin_role": "admin",
            "admin_user_id": user_id,
            "admin_username": f"admin{user_id}@example.com",
        }
        # Emulate sync Starlette-Admin session object in request.state.session.
        self.state = SimpleNamespace(admin_user=None, session=object())
        self._form_data = form_data

    async def form(self):
        return self._form_data


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeAsyncSessionCtx:
    def __init__(self, user):
        self._user = user
        self.committed = False
        self.no_autoflush = _NoopContext()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        del stmt
        return _FakeScalarResult(self._user)

    async def commit(self):
        self.committed = True


class _NoopContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


async def test_ai_job_admin_before_create_uses_dedicated_async_session_for_snapshot(monkeypatch):
    admin = SimpleNamespace(id=404, role="admin", username="admin404@example.com")
    request = _DummyActionRequest(user_id=admin.id, form_data={})
    obj = AIGamificationJob()
    captured: dict[str, object] = {}

    async def _fake_snapshot_builder(session, payload, current_user):
        captured["session"] = session
        captured["source_type"] = payload.source_type.value
        captured["source_id"] = payload.source_id
        captured["user_id"] = current_user.id
        captured["user_role"] = current_user.role
        return "snapshot-text"

    fake_ctx = _FakeAsyncSessionCtx(admin)
    monkeypatch.setattr("app.admin.views_gamification.AsyncSessionLocal", lambda: fake_ctx)
    monkeypatch.setattr("app.admin.views_gamification.build_source_snapshot", _fake_snapshot_builder)

    view = AIGamificationJobReadOnlyView(AIGamificationJob)
    await view.before_create(
        request,
        data={"source_type": "material", "source_id": 9, "language": "ru", "constraints_json": {"": ""}},
        obj=obj,
    )

    assert captured["session"] is fake_ctx
    assert captured["source_type"] == "material"
    assert captured["source_id"] == 9
    assert captured["user_id"] == 404
    assert captured["user_role"] == "admin"
    assert obj.created_by_user_id == 404
    assert obj.status == "pending"
    assert obj.source_snapshot == "snapshot-text"


async def test_ai_job_admin_apply_row_action_works_with_sync_request_session(monkeypatch):
    admin = SimpleNamespace(id=101, role="admin", username="admin101@example.com")

    captured: dict[str, object] = {}

    async def _fake_get_job_for_user(session, job_id: int, current_user):
        captured["job_id"] = job_id
        captured["current_user_id"] = current_user.id
        captured["session_type"] = type(session).__name__
        return object()

    async def _fake_apply_job_draft(session, *, job_id: int, payload, current_user):
        captured["apply_job_id"] = job_id
        captured["target_id"] = payload.target_id
        captured["target_type"] = payload.target_type.value
        captured["apply_user_id"] = current_user.id
        return {"job_id": job_id, "status": "applied", "updated_entity": {"type": payload.target_type.value, "id": payload.target_id}}

    monkeypatch.setattr("app.admin.views_gamification.AsyncSessionLocal", lambda: _FakeAsyncSessionCtx(admin))
    monkeypatch.setattr("app.admin.views_gamification.get_job_for_user", _fake_get_job_for_user)
    monkeypatch.setattr("app.admin.views_gamification.apply_job_draft", _fake_apply_job_draft)

    view = AIGamificationJobReadOnlyView(AIGamificationJob)
    request = _DummyActionRequest(
        user_id=admin.id,
        form_data={"target_type": "question", "target_id": "112", "apply_mode": "append"},
    )

    message = await view.apply_draft_row_action(request, pk="6")

    assert message == "AI job #6 applied to question #112"
    assert captured["job_id"] == 6
    assert captured["apply_job_id"] == 6
    assert captured["target_id"] == 112
    assert captured["target_type"] == "question"
    assert captured["current_user_id"] == admin.id
    assert captured["apply_user_id"] == admin.id


async def test_ai_job_admin_apply_row_action_accepts_auto_target(monkeypatch):
    admin = SimpleNamespace(id=303, role="admin", username="admin303@example.com")

    captured: dict[str, object] = {}

    async def _fake_get_job_for_user(session, job_id: int, current_user):
        del session
        captured["job_id"] = job_id
        captured["current_user_id"] = current_user.id
        return object()

    async def _fake_apply_job_draft(session, *, job_id: int, payload, current_user):
        del session
        captured["payload_target_type"] = payload.target_type
        captured["payload_target_id"] = payload.target_id
        captured["apply_user_id"] = current_user.id
        return {"job_id": job_id, "status": "applied", "updated_entity": {"type": "question", "id": 112}}

    monkeypatch.setattr("app.admin.views_gamification.AsyncSessionLocal", lambda: _FakeAsyncSessionCtx(admin))
    monkeypatch.setattr("app.admin.views_gamification.get_job_for_user", _fake_get_job_for_user)
    monkeypatch.setattr("app.admin.views_gamification.apply_job_draft", _fake_apply_job_draft)

    view = AIGamificationJobReadOnlyView(AIGamificationJob)
    request = _DummyActionRequest(user_id=admin.id, form_data={"target_type": "", "target_id": "", "apply_mode": "append"})

    message = await view.apply_draft_row_action(request, pk="6")

    assert message == "AI job #6 applied to question #112"
    assert captured["job_id"] == 6
    assert captured["current_user_id"] == admin.id
    assert captured["apply_user_id"] == admin.id
    assert captured["payload_target_type"] is None
    assert captured["payload_target_id"] is None


async def test_ai_job_admin_retry_row_action_works_with_sync_request_session(monkeypatch):
    admin = SimpleNamespace(id=202, role="admin", username="admin202@example.com")

    captured: dict[str, object] = {}

    async def _fake_retry(session, *, job_id: int, current_user):
        captured["job_id"] = job_id
        captured["current_user_id"] = current_user.id
        captured["session_type"] = type(session).__name__
        return {"job_id": job_id, "status": "pending"}

    monkeypatch.setattr("app.admin.views_gamification.AsyncSessionLocal", lambda: _FakeAsyncSessionCtx(admin))
    monkeypatch.setattr("app.admin.views_gamification.retry_ai_gamification_job", _fake_retry)

    view = AIGamificationJobReadOnlyView(AIGamificationJob)
    request = _DummyActionRequest(user_id=admin.id, form_data={})

    message = await view.retry_job_row_action(request, pk="9")

    assert message == "AI job #9 moved to status 'pending'"
    assert captured["job_id"] == 9
    assert captured["current_user_id"] == admin.id


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


async def test_level_admin_view_after_actions_invalidate_related_caches(monkeypatch):
    captured_calls: list[tuple[str, ...]] = []

    async def _fake_bump_cache_namespace(*namespaces: str):
        captured_calls.append(tuple(namespaces))

    monkeypatch.setattr("app.admin.views_content.bump_cache_namespace", _fake_bump_cache_namespace)

    view = LevelAdminView(Level)
    request = _DummyAdminRequest(db=object(), user_id=1)
    level = Level(name="Cache Level", required_points=1)

    await view.after_create(request, level)
    await view.after_edit(request, level)
    await view.after_delete(request, level)

    assert len(captured_calls) == 3
    for call in captured_calls:
        assert set(call) == {"levels", "tests", "materials"}

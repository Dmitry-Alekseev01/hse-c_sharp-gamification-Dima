import logging
from typing import Any

from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.models.ai_gamification_job import AIGamificationJob
from app.models.analytics import Analytics
from app.models.answer import Answer
from app.models.challenge import Challenge, UserChallengeClaim, UserChallengeProgress
from app.models.choice import Choice
from app.models.group import GroupMembership, StudyGroup
from app.models.level import Level
from app.models.points_ledger import PointsLedger
from app.models.material import Material
from app.models.question import Question
from app.models.reward_definition import RewardDefinition
from app.models.season import LeaderboardSnapshot, Season
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.models.unlock_rule import UnlockRule
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.models.user_reward import UserReward

logger = logging.getLogger(__name__)


class AdminAuditedModelView(ModelView):
    # Disable batch actions by default for safer admin operations.
    actions: list[str] = []

    def _is_admin(self, request: Request) -> bool:
        return str(request.session.get("admin_role", "")).lower() == "admin"

    def can_create(self, request: Request) -> bool:
        return self._is_admin(request)

    def can_edit(self, request: Request) -> bool:
        return self._is_admin(request)

    def can_delete(self, request: Request) -> bool:
        return self._is_admin(request)

    def _actor(self, request: Request) -> str:
        admin_user = getattr(request.state, "admin_user", None)
        username = getattr(admin_user, "username", None)
        if username:
            return str(username)
        return str(request.session.get("admin_username", "unknown"))

    def _model_name(self) -> str:
        model = getattr(self, "model", None)
        return getattr(model, "__name__", str(model))

    def _audit(self, request: Request, action: str, obj: Any | None = None) -> None:
        obj_id = getattr(obj, "id", None) if obj is not None else None
        logger.info(
            "admin_audit action=%s model=%s actor=%s obj_id=%s",
            action,
            self._model_name(),
            self._actor(request),
            obj_id,
        )

    def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        del data, obj
        self._audit(request, "before_create")

    def after_create(self, request: Request, obj: Any) -> None:
        self._audit(request, "after_create", obj)

    def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        del data
        self._audit(request, "before_edit", obj)

    def after_edit(self, request: Request, obj: Any) -> None:
        self._audit(request, "after_edit", obj)

    def before_delete(self, request: Request, obj: Any) -> None:
        self._audit(request, "before_delete", obj)

    def after_delete(self, request: Request, obj: Any) -> None:
        self._audit(request, "after_delete", obj)

    def _validate_required_str(
        self,
        data: dict[str, Any],
        field: str,
        errors: dict[str, list[str]],
        *,
        max_len: int | None = None,
    ) -> None:
        value = data.get(field)
        if value is None or not str(value).strip():
            errors.setdefault(field, []).append("Field is required")
            return
        if max_len is not None and len(str(value)) > max_len:
            errors.setdefault(field, []).append(f"Must be <= {max_len} characters")

    def _validate_optional_int_min(
        self,
        data: dict[str, Any],
        field: str,
        errors: dict[str, list[str]],
        *,
        minimum: int = 0,
    ) -> None:
        raw_value = data.get(field)
        if raw_value in (None, ""):
            return
        try:
            numeric_value = int(raw_value)
        except (TypeError, ValueError):
            errors.setdefault(field, []).append("Must be an integer")
            return
        if numeric_value < minimum:
            errors.setdefault(field, []).append(f"Must be >= {minimum}")

    def _validate_optional_float_min(
        self,
        data: dict[str, Any],
        field: str,
        errors: dict[str, list[str]],
        *,
        minimum: float = 0.0,
        strict_gt: bool = False,
    ) -> None:
        raw_value = data.get(field)
        if raw_value in (None, ""):
            return
        try:
            numeric_value = float(raw_value)
        except (TypeError, ValueError):
            errors.setdefault(field, []).append("Must be a number")
            return
        if strict_gt and numeric_value <= minimum:
            errors.setdefault(field, []).append(f"Must be > {minimum}")
        elif not strict_gt and numeric_value < minimum:
            errors.setdefault(field, []).append(f"Must be >= {minimum}")


class ReadOnlyAdminView(AdminAuditedModelView):
    row_actions = ["view"]

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return False

    def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request, data
        return None


class UserReadOnlyView(AdminAuditedModelView):
    name = "Users"
    icon = "fa fa-users"
    fields = ["id", "username", "full_name", "role", "created_at"]
    row_actions = ["view"]
    searchable_fields = ["username", "full_name", "role"]
    sortable_fields = ["id", "username", "role", "created_at"]

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return False

    def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request, data
        return None


class MaterialAdminView(AdminAuditedModelView):
    name = "Materials"
    icon = "fa fa-book"
    fields = [
        "id",
        "title",
        "material_type",
        "status",
        "description",
        "published_at",
        "author_id",
        "required_level_id",
    ]
    searchable_fields = ["title", "description"]
    sortable_fields = ["id", "title", "material_type", "status", "published_at", "author_id", "required_level_id"]

    def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "title", errors, max_len=300)
        material_type = data.get("material_type")
        if material_type not in {"lesson", "module", "article"}:
            errors.setdefault("material_type", []).append("Must be one of: lesson, module, article")
        status = data.get("status")
        if status not in {"draft", "published", "archived"}:
            errors.setdefault("status", []).append("Must be one of: draft, published, archived")
        if errors:
            raise FormValidationError(errors)


class TestAdminView(AdminAuditedModelView):
    name = "Tests"
    icon = "fa fa-file-lines"
    fields = [
        "id",
        "title",
        "description",
        "time_limit_minutes",
        "max_score",
        "published",
        "published_at",
        "material_id",
        "deadline",
        "author_id",
        "required_level_id",
    ]
    searchable_fields = ["title", "description"]
    sortable_fields = [
        "id",
        "title",
        "time_limit_minutes",
        "max_score",
        "published",
        "published_at",
        "material_id",
        "author_id",
        "required_level_id",
        "deadline",
    ]

    def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "title", errors, max_len=300)
        self._validate_optional_int_min(data, "time_limit_minutes", errors, minimum=1)
        self._validate_optional_float_min(data, "max_score", errors, minimum=0.0)
        if errors:
            raise FormValidationError(errors)


class QuestionAdminView(AdminAuditedModelView):
    name = "Questions"
    icon = "fa fa-circle-question"
    fields = ["id", "test_id", "text", "points", "is_open_answer", "material_urls"]
    searchable_fields = ["text"]
    sortable_fields = ["id", "test_id", "points", "is_open_answer"]

    def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "text", errors)
        self._validate_optional_float_min(data, "points", errors, minimum=0.0, strict_gt=True)
        if errors:
            raise FormValidationError(errors)


class ChoiceAdminView(AdminAuditedModelView):
    name = "Choices"
    icon = "fa fa-list"
    fields = ["id", "question_id", "value", "ordinal", "is_correct"]
    searchable_fields = ["value"]
    sortable_fields = ["id", "question_id", "ordinal", "is_correct"]

    def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "value", errors, max_len=1000)
        self._validate_optional_int_min(data, "ordinal", errors, minimum=0)
        if errors:
            raise FormValidationError(errors)


class LevelAdminView(AdminAuditedModelView):
    name = "Levels"
    icon = "fa fa-signal"
    fields = ["id", "name", "required_points", "description"]
    searchable_fields = ["name", "description"]
    sortable_fields = ["id", "name", "required_points"]

    def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "name", errors, max_len=200)
        self._validate_optional_int_min(data, "required_points", errors, minimum=0)
        if errors:
            raise FormValidationError(errors)


class StudyGroupReadOnlyView(ReadOnlyAdminView):
    name = "Study Groups"
    icon = "fa fa-users-rectangle"
    fields = ["id", "name", "teacher_id"]
    searchable_fields = ["name"]
    sortable_fields = ["id", "name", "teacher_id"]


class GroupMembershipReadOnlyView(ReadOnlyAdminView):
    name = "Group Memberships"
    icon = "fa fa-user-group"
    fields = ["id", "group_id", "user_id"]
    sortable_fields = ["id", "group_id", "user_id"]


class AnalyticsReadOnlyView(ReadOnlyAdminView):
    name = "Analytics"
    icon = "fa fa-chart-line"
    fields = ["id", "user_id", "total_points", "tests_taken", "last_active", "streak_days", "current_level_id"]
    sortable_fields = ["id", "user_id", "total_points", "tests_taken", "streak_days", "current_level_id", "last_active"]


class TestAttemptReadOnlyView(ReadOnlyAdminView):
    name = "Test Attempts"
    icon = "fa fa-stopwatch"
    fields = [
        "id",
        "user_id",
        "test_id",
        "status",
        "score",
        "manual_score",
        "max_score",
        "time_spent_seconds",
        "started_at",
        "submitted_at",
        "completed_at",
    ]
    sortable_fields = [
        "id",
        "user_id",
        "test_id",
        "status",
        "score",
        "max_score",
        "time_spent_seconds",
        "started_at",
        "completed_at",
    ]


class AnswerReadOnlyView(ReadOnlyAdminView):
    name = "Answers"
    icon = "fa fa-reply"
    fields = [
        "id",
        "user_id",
        "test_id",
        "attempt_id",
        "question_id",
        "answer_payload",
        "score",
        "graded_by",
        "graded_at",
        "created_at",
    ]
    sortable_fields = ["id", "user_id", "test_id", "question_id", "score", "graded_by", "graded_at", "created_at"]


class PointsLedgerReadOnlyView(ReadOnlyAdminView):
    name = "Points Ledger"
    icon = "fa fa-coins"
    fields = ["id", "user_id", "delta", "reason_code", "source_type", "source_id", "idempotency_key", "created_at"]
    sortable_fields = ["id", "user_id", "delta", "reason_code", "source_type", "source_id", "created_at"]


class UserAchievementReadOnlyView(ReadOnlyAdminView):
    name = "User Achievements"
    icon = "fa fa-award"
    fields = ["id", "user_id", "achievement_id", "source_event", "earned_at"]
    sortable_fields = ["id", "user_id", "achievement_id", "earned_at"]


class UserRewardReadOnlyView(ReadOnlyAdminView):
    name = "User Rewards"
    icon = "fa fa-medal"
    fields = ["id", "user_id", "reward_definition_id", "source_type", "source_ref", "earned_at"]
    sortable_fields = ["id", "user_id", "reward_definition_id", "source_type", "earned_at"]


class RewardDefinitionReadOnlyView(ReadOnlyAdminView):
    name = "Reward Definitions"
    icon = "fa fa-gift"
    fields = ["id", "code", "title", "description", "reward_type", "payload_json", "is_active", "created_at", "updated_at"]
    searchable_fields = ["code", "title", "reward_type"]
    sortable_fields = ["id", "code", "title", "reward_type", "is_active", "created_at", "updated_at"]


class UnlockRuleReadOnlyView(ReadOnlyAdminView):
    name = "Unlock Rules"
    icon = "fa fa-unlock"
    fields = ["id", "reward_definition_id", "source_type", "source_code", "min_level_required", "is_active", "created_at", "updated_at"]
    sortable_fields = ["id", "reward_definition_id", "source_type", "source_code", "min_level_required", "is_active"]


class ChallengeReadOnlyView(ReadOnlyAdminView):
    name = "Challenges"
    icon = "fa fa-flag-checkered"
    fields = [
        "id",
        "code",
        "title",
        "description",
        "period_type",
        "event_type",
        "target_value",
        "reward_points",
        "is_active",
        "starts_at",
        "ends_at",
        "created_by",
        "created_at",
        "updated_at",
    ]
    searchable_fields = ["code", "title", "event_type", "period_type"]
    sortable_fields = ["id", "code", "event_type", "period_type", "target_value", "reward_points", "is_active", "created_at"]


class UserChallengeProgressReadOnlyView(ReadOnlyAdminView):
    name = "Challenge Progress"
    icon = "fa fa-list-check"
    fields = ["id", "user_id", "challenge_id", "period_key", "progress_value", "completed_at", "created_at", "updated_at"]
    sortable_fields = ["id", "user_id", "challenge_id", "period_key", "progress_value", "completed_at", "created_at"]


class UserChallengeClaimReadOnlyView(ReadOnlyAdminView):
    name = "Challenge Claims"
    icon = "fa fa-check-double"
    fields = ["id", "user_id", "challenge_id", "period_key", "reward_points", "ledger_entry_id", "claimed_at"]
    sortable_fields = ["id", "user_id", "challenge_id", "period_key", "reward_points", "claimed_at"]


class AIGamificationJobReadOnlyView(ReadOnlyAdminView):
    name = "AI Jobs"
    icon = "fa fa-robot"
    fields = [
        "id",
        "created_by_user_id",
        "status",
        "source_type",
        "source_id",
        "target_level",
        "language",
        "style",
        "tone",
        "model",
        "provider",
        "latency_ms",
        "error_text",
        "started_at",
        "completed_at",
        "applied_at",
        "applied_target_type",
        "applied_target_id",
        "created_at",
        "updated_at",
    ]
    searchable_fields = ["status", "source_type", "language", "style", "tone", "model", "provider"]
    sortable_fields = ["id", "created_by_user_id", "status", "source_type", "latency_ms", "created_at", "completed_at", "applied_at"]


class SeasonReadOnlyView(ReadOnlyAdminView):
    name = "Seasons"
    icon = "fa fa-calendar"
    fields = ["id", "code", "title", "starts_at", "ends_at", "is_active", "created_by", "created_at", "updated_at"]
    searchable_fields = ["code", "title"]
    sortable_fields = ["id", "code", "starts_at", "ends_at", "is_active", "created_at"]


class LeaderboardSnapshotReadOnlyView(ReadOnlyAdminView):
    name = "Leaderboard Snapshots"
    icon = "fa fa-trophy"
    fields = ["id", "scope", "period", "group_id", "season_id", "user_id", "rank", "total_points", "bucket_start", "computed_at"]
    sortable_fields = ["id", "scope", "period", "group_id", "season_id", "user_id", "rank", "total_points", "bucket_start", "computed_at"]


def get_admin_views() -> list[ModelView]:
    return [
        UserReadOnlyView(User),
        LevelAdminView(Level),
        MaterialAdminView(Material),
        TestAdminView(Test),
        QuestionAdminView(Question),
        ChoiceAdminView(Choice),
        StudyGroupReadOnlyView(StudyGroup),
        GroupMembershipReadOnlyView(GroupMembership),
        AnalyticsReadOnlyView(Analytics),
        TestAttemptReadOnlyView(TestAttempt),
        AnswerReadOnlyView(Answer),
        PointsLedgerReadOnlyView(PointsLedger),
        UserAchievementReadOnlyView(UserAchievement),
        UserRewardReadOnlyView(UserReward),
        RewardDefinitionReadOnlyView(RewardDefinition),
        UnlockRuleReadOnlyView(UnlockRule),
        ChallengeReadOnlyView(Challenge),
        UserChallengeProgressReadOnlyView(UserChallengeProgress),
        UserChallengeClaimReadOnlyView(UserChallengeClaim),
        AIGamificationJobReadOnlyView(AIGamificationJob),
        SeasonReadOnlyView(Season),
        LeaderboardSnapshotReadOnlyView(LeaderboardSnapshot),
    ]

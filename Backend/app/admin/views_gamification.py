from typing import Any

from starlette.requests import Request
from starlette_admin.actions import row_action
from starlette_admin.exceptions import ActionFailed, FormValidationError

from app.models.ai_gamification_job import AIGamificationJob
from app.models.achievement_definition import AchievementDefinition
from app.models.challenge import Challenge, UserChallengeClaim, UserChallengeProgress
from app.models.reward_definition import RewardDefinition
from app.models.season import LeaderboardSnapshot, Season
from app.models.unlock_rule import UnlockRule
from app.models.user import User
from app.schemas.ai_gamification import AIGamifyApplyRequest, AIGamifyRequest
from app.services.ai_gamification_service import (
    apply_job_draft,
    build_source_snapshot,
    enqueue_ai_job,
    get_job_for_user,
    retry_ai_gamification_job,
)

from .views_base import AdminAuditedModelView, ReadOnlyAdminView, TeacherAccessibleModelView


class RewardDefinitionAdminView(AdminAuditedModelView):
    name = "Reward Definitions"
    icon = "fa fa-gift"
    fields = ["id", "code", "title", "description", "reward_type", "payload_json", "is_active", "created_at", "updated_at"]
    searchable_fields = ["code", "title", "reward_type"]
    sortable_fields = ["id", "code", "title", "reward_type", "is_active", "created_at", "updated_at"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "code", errors, max_len=100)
        self._validate_required_str(data, "title", errors, max_len=200)
        reward_type = data.get("reward_type")
        if reward_type is None or not str(reward_type).strip():
            errors.setdefault("reward_type", []).append("Field is required")
        if errors:
            raise FormValidationError(errors)


class AchievementDefinitionAdminView(AdminAuditedModelView):
    name = "Achievement Definitions"
    icon = "fa fa-star"
    fields = [
        "id",
        "code",
        "title",
        "description",
        "reward",
        "criteria_type",
        "threshold_value",
        "is_active",
        "created_at",
        "updated_at",
    ]
    searchable_fields = ["code", "title", "criteria_type"]
    sortable_fields = ["id", "code", "title", "criteria_type", "threshold_value", "is_active", "created_at"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "code", errors, max_len=100)
        self._validate_required_str(data, "title", errors, max_len=200)
        self._validate_required_str(data, "description", errors)
        criteria_type = data.get("criteria_type")
        if criteria_type not in {"total_points", "streak_days", "completed_attempts"}:
            errors.setdefault("criteria_type", []).append(
                "Must be one of: total_points, streak_days, completed_attempts"
            )
        self._validate_required_int_min(data, "threshold_value", errors, minimum=1)
        if errors:
            raise FormValidationError(errors)


class UnlockRuleAdminView(AdminAuditedModelView):
    name = "Unlock Rules"
    icon = "fa fa-unlock"
    fields = ["id", "reward_definition", "source_type", "source_code", "min_level_required", "is_active", "created_at", "updated_at"]
    sortable_fields = ["id", "reward_definition_id", "source_type", "source_code", "min_level_required", "is_active"]
    fields_default_sort = ["reward_definition_id asc", "id asc"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        reward_definition_id, reward_definition_id_error = self._extract_foreign_id(
            data,
            id_field="reward_definition_id",
            relation_field="reward_definition",
        )
        if reward_definition_id_error is not None:
            errors.setdefault("reward_definition_id", []).append(reward_definition_id_error)
        elif reward_definition_id is None:
            errors.setdefault("reward_definition_id", []).append("Field is required")
        elif reward_definition_id < 1:
            errors.setdefault("reward_definition_id", []).append("Must be >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=RewardDefinition,
                model_id=reward_definition_id,
                errors=errors,
                field="reward_definition_id",
                message="Must reference an existing reward definition",
            )
        source_type = data.get("source_type")
        if source_type not in {"achievement", "challenge", "level"}:
            errors.setdefault("source_type", []).append("Must be one of: achievement, challenge, level")
        self._validate_optional_int_min(data, "min_level_required", errors, minimum=1)
        if errors:
            raise FormValidationError(errors)


class ChallengeAdminView(AdminAuditedModelView):
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

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "code", errors, max_len=100)
        self._validate_required_str(data, "title", errors, max_len=200)
        period_type = data.get("period_type")
        if period_type not in {"daily", "weekly"}:
            errors.setdefault("period_type", []).append("Must be one of: daily, weekly")
        event_type = data.get("event_type")
        if event_type not in {"answer_submitted", "attempt_completed", "streak_day"}:
            errors.setdefault("event_type", []).append(
                "Must be one of: answer_submitted, attempt_completed, streak_day"
            )
        self._validate_required_int_min(data, "target_value", errors, minimum=1)
        self._validate_optional_float_min(data, "reward_points", errors, minimum=0.0)
        raw_created_by = data.get("created_by")
        if raw_created_by not in (None, ""):
            created_by = self._to_int_or_none(raw_created_by)
            if created_by is None:
                errors.setdefault("created_by", []).append("Must be an integer")
            elif created_by < 1:
                errors.setdefault("created_by", []).append("Must be >= 1")
            else:
                await self._validate_existing_fk(
                    request,
                    model=User,
                    model_id=created_by,
                    errors=errors,
                    field="created_by",
                    message="Must reference an existing user",
                )
        starts_at = self._to_datetime_or_none(data.get("starts_at"))
        ends_at = self._to_datetime_or_none(data.get("ends_at"))
        if starts_at is not None and ends_at is not None and starts_at > ends_at:
            errors.setdefault("ends_at", []).append("ends_at must be >= starts_at")
        if errors:
            raise FormValidationError(errors)


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


class AIGamificationJobReadOnlyView(TeacherAccessibleModelView):
    name = "AI Jobs"
    icon = "fa fa-robot"
    row_actions = ["view", "apply_draft", "retry_job"]
    fields = [
        "id",
        "created_by_user_id",
        "status",
        "source_type",
        "source_id",
        "raw_text",
        "source_snapshot",
        "target_level",
        "language",
        "style",
        "tone",
        "constraints_json",
        "draft_json",
        "model",
        "provider",
        "usage_json",
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
    exclude_fields_from_create = [
        "id",
        "created_by_user_id",
        "status",
        "source_snapshot",
        "draft_json",
        "model",
        "provider",
        "usage_json",
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

    _APPLY_ACTION_FORM = """
<form>
  <div class="mb-3">
    <label class="form-label" for="apply-target-type">Target type</label>
    <select id="apply-target-type" class="form-select" name="target_type" required>
      <option value="material">material</option>
      <option value="question">question</option>
    </select>
  </div>
  <div class="mb-3">
    <label class="form-label" for="apply-target-id">Target ID</label>
    <input id="apply-target-id" class="form-control" type="number" min="1" step="1" name="target_id" required>
  </div>
  <div class="mb-3">
    <label class="form-label" for="apply-mode">Apply mode</label>
    <select id="apply-mode" class="form-select" name="apply_mode" required>
      <option value="append">append</option>
      <option value="replace">replace</option>
    </select>
  </div>
</form>
""".strip()

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return False

    def _scope_to_creator(self, request: Request, stmt):
        if self._is_teacher(request):
            stmt = stmt.where(self.model.created_by_user_id == self._teacher_id(request))
        return stmt

    def get_list_query(self, request: Request):
        stmt = super().get_list_query(request)
        return self._scope_to_creator(request, stmt)

    def get_details_query(self, request: Request):
        stmt = super().get_details_query(request)
        return self._scope_to_creator(request, stmt)

    @staticmethod
    def _normalize_constraints(raw_constraints: Any) -> tuple[list[str], str | None]:
        if raw_constraints in (None, ""):
            return [], None
        if not isinstance(raw_constraints, (list, tuple)):
            return [], "constraints_json must be a JSON array of strings"
        normalized: list[str] = []
        for item in raw_constraints:
            if item in (None, ""):
                continue
            text = str(item).strip()
            if text:
                normalized.append(text)
        return normalized, None

    def _build_create_payload(self, data: dict[str, Any]) -> AIGamifyRequest:
        errors: dict[str, list[str]] = {}
        source_type = str(data.get("source_type") or "").strip()
        source_id = self._to_int_or_none(data.get("source_id"))
        raw_text_value = data.get("raw_text")
        raw_text = None if raw_text_value in (None, "") else str(raw_text_value)
        target_level = str(data.get("target_level") or "").strip() or None
        language = str(data.get("language") or "ru").strip() or "ru"
        style = str(data.get("style") or "").strip() or None
        tone = str(data.get("tone") or "").strip() or None
        constraints, constraints_error = self._normalize_constraints(data.get("constraints_json"))

        if constraints_error is not None:
            errors.setdefault("constraints_json", []).append(constraints_error)
        if source_type not in {"material", "question", "raw_text"}:
            errors.setdefault("source_type", []).append("Must be one of: material, question, raw_text")
        if source_type in {"material", "question"}:
            if source_id is None or source_id < 1:
                errors.setdefault("source_id", []).append("Must be a positive integer for material/question source")
        if source_type == "raw_text" and not raw_text:
            errors.setdefault("raw_text", []).append("raw_text is required when source_type=raw_text")
        if errors:
            raise FormValidationError(errors)

        payload_dict: dict[str, Any] = {
            "source_type": source_type,
            "source_id": source_id,
            "raw_text": raw_text,
            "target_level": target_level,
            "language": language,
            "style": style,
            "tone": tone,
            "constraints": constraints,
        }
        try:
            return AIGamifyRequest.model_validate(payload_dict)
        except Exception as exc:
            raise FormValidationError({"_schema": [self._humanize_action_error(exc)]})

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        # Validate create payload semantics with the same schema used by API.
        self._build_create_payload(data)

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        payload = self._build_create_payload(data)
        admin_user = getattr(request.state, "admin_user", None)
        if admin_user is None:
            raise FormValidationError({"_schema": ["Unable to resolve admin identity"]})
        source_snapshot = await build_source_snapshot(request.state.session, payload, admin_user)

        data["created_by_user_id"] = int(admin_user.id)
        data["status"] = "pending"
        data["source_type"] = payload.source_type.value
        data["source_id"] = payload.source_id
        data["raw_text"] = payload.raw_text
        data["source_snapshot"] = source_snapshot
        data["target_level"] = payload.target_level.value if payload.target_level else None
        data["language"] = payload.language
        data["style"] = payload.style.value if payload.style else None
        data["tone"] = payload.tone.value if payload.tone else None
        data["constraints_json"] = list(payload.constraints or [])
        data["draft_json"] = None
        data["model"] = None
        data["provider"] = None
        data["usage_json"] = None
        data["latency_ms"] = None
        data["error_text"] = None
        data["started_at"] = None
        data["completed_at"] = None
        data["applied_at"] = None
        data["applied_target_type"] = None
        data["applied_target_id"] = None
        await super().before_create(request, data, obj)

    async def after_create(self, request: Request, obj: Any) -> None:
        await super().after_create(request, obj)
        try:
            # Ensure object is committed before enqueue to avoid worker race with uncommitted row.
            await self._commit_session(request)
            await enqueue_ai_job(int(obj.id))
        except Exception as exc:
            obj.status = "failed"
            obj.error_text = f"Queue unavailable: {self._humanize_action_error(exc)}"
            await self._commit_session(request)
            raise ActionFailed("AI job was created but could not be enqueued")

    @row_action(
        name="retry_job",
        text="Retry",
        confirmation="Retry this failed AI job?",
        icon_class="fa fa-rotate-right",
        submit_btn_text="Retry",
        submit_btn_class="btn-warning",
        action_btn_class="btn-outline-warning",
    )
    async def retry_job_row_action(self, request: Request, pk: Any) -> str:
        admin_user = getattr(request.state, "admin_user", None)
        if admin_user is None:
            raise ActionFailed("Unable to resolve admin identity")
        session = request.state.session
        try:
            payload = await retry_ai_gamification_job(session, job_id=int(pk), current_user=admin_user)
            await self._commit_session(request)
            return f"AI job #{payload['job_id']} moved to status '{payload['status']}'"
        except Exception as exc:
            await self._rollback_session(request)
            raise ActionFailed(self._humanize_action_error(exc))

    @row_action(
        name="apply_draft",
        text="Apply Draft",
        confirmation="Apply this completed AI draft to target?",
        icon_class="fa fa-bolt",
        submit_btn_text="Apply",
        submit_btn_class="btn-success",
        action_btn_class="btn-outline-success",
        form=_APPLY_ACTION_FORM,
    )
    async def apply_draft_row_action(self, request: Request, pk: Any) -> str:
        admin_user = getattr(request.state, "admin_user", None)
        if admin_user is None:
            raise ActionFailed("Unable to resolve admin identity")

        form_data = await request.form()
        target_type = str(form_data.get("target_type") or "").strip()
        target_id = self._to_int_or_none(form_data.get("target_id"))
        apply_mode = str(form_data.get("apply_mode") or "append").strip()
        if target_id is None or target_id < 1:
            raise ActionFailed("target_id must be a positive integer")

        try:
            payload = AIGamifyApplyRequest.model_validate(
                {
                    "target_type": target_type,
                    "target_id": target_id,
                    "apply_mode": apply_mode,
                }
            )
        except Exception as exc:
            raise ActionFailed(self._humanize_action_error(exc))

        session = request.state.session
        try:
            await get_job_for_user(session, int(pk), admin_user)
            applied = await apply_job_draft(
                session,
                job_id=int(pk),
                payload=payload,
                current_user=admin_user,
            )
            await self._commit_session(request)
            return (
                f"AI job #{applied['job_id']} applied to "
                f"{applied['updated_entity']['type']} #{applied['updated_entity']['id']}"
            )
        except Exception as exc:
            await self._rollback_session(request)
            raise ActionFailed(self._humanize_action_error(exc))


class SeasonAdminView(AdminAuditedModelView):
    name = "Seasons"
    icon = "fa fa-calendar"
    fields = ["id", "code", "title", "starts_at", "ends_at", "is_active", "created_by", "created_at", "updated_at"]
    searchable_fields = ["code", "title"]
    sortable_fields = ["id", "code", "starts_at", "ends_at", "is_active", "created_at"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "code", errors, max_len=100)
        self._validate_required_str(data, "title", errors, max_len=200)
        starts_raw = data.get("starts_at")
        ends_raw = data.get("ends_at")
        if starts_raw in (None, ""):
            errors.setdefault("starts_at", []).append("Field is required")
        if ends_raw in (None, ""):
            errors.setdefault("ends_at", []).append("Field is required")
        starts_at = self._to_datetime_or_none(starts_raw)
        ends_at = self._to_datetime_or_none(ends_raw)
        if starts_raw not in (None, "") and starts_at is None:
            errors.setdefault("starts_at", []).append("Must be a valid datetime")
        if ends_raw not in (None, "") and ends_at is None:
            errors.setdefault("ends_at", []).append("Must be a valid datetime")
        if starts_at is not None and ends_at is not None and starts_at > ends_at:
            errors.setdefault("ends_at", []).append("ends_at must be >= starts_at")
        raw_created_by = data.get("created_by")
        if raw_created_by not in (None, ""):
            created_by = self._to_int_or_none(raw_created_by)
            if created_by is None:
                errors.setdefault("created_by", []).append("Must be an integer")
            elif created_by < 1:
                errors.setdefault("created_by", []).append("Must be >= 1")
            else:
                await self._validate_existing_fk(
                    request,
                    model=User,
                    model_id=created_by,
                    errors=errors,
                    field="created_by",
                    message="Must reference an existing user",
                )
        if errors:
            raise FormValidationError(errors)


class LeaderboardSnapshotReadOnlyView(ReadOnlyAdminView):
    name = "Leaderboard Snapshots"
    icon = "fa fa-trophy"
    fields = ["id", "scope", "period", "group_id", "season_id", "user_id", "rank", "total_points", "bucket_start", "computed_at"]
    sortable_fields = ["id", "scope", "period", "group_id", "season_id", "user_id", "rank", "total_points", "bucket_start", "computed_at"]

import logging
from typing import Any

import anyio
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.models.ai_gamification_job import AIGamificationJob
from app.models.achievement_definition import AchievementDefinition
from app.models.analytics import Analytics
from app.models.answer import Answer
from app.models.challenge import Challenge, UserChallengeClaim, UserChallengeProgress
from app.models.choice import Choice
from app.models.group import GroupMembership, StudyGroup
from app.models.level import Level
from app.models.material_attachment import MaterialAttachment
from app.models.material_block import MaterialBlock
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
from app.cache.redis_cache import (
    NS_MATERIALS,
    NS_TEST_CONTENT,
    NS_TESTS,
    NS_TEST_SUMMARY,
    bump_cache_namespace,
)
from app.core.material_taxonomy import MATERIAL_ATTACHMENT_KIND_VALUES, MATERIAL_BLOCK_TYPE_VALUES

logger = logging.getLogger(__name__)
MATERIAL_BLOCK_TYPE_VALUES_SET = set(MATERIAL_BLOCK_TYPE_VALUES)
MATERIAL_ATTACHMENT_KIND_VALUES_SET = set(MATERIAL_ATTACHMENT_KIND_VALUES)


class AdminAuditedModelView(ModelView):
    # Disable batch actions by default for safer admin operations.
    actions: list[str] = []

    def _role(self, request: Request) -> str:
        return str(request.session.get("admin_role", "")).lower()

    def _is_admin(self, request: Request) -> bool:
        return self._role(request) == "admin"

    def _is_teacher(self, request: Request) -> bool:
        return self._role(request) == "teacher"

    def is_accessible(self, request: Request) -> bool:
        return self._is_admin(request)

    def _resolve_admin_user_id(self, request: Request) -> int | None:
        admin_user = getattr(request.state, "admin_user", None)
        state_id = getattr(admin_user, "id", None)
        if state_id is not None:
            try:
                return int(state_id)
            except (TypeError, ValueError):
                return None
        raw_user_id = request.session.get("admin_user_id")
        if raw_user_id is None:
            return None
        try:
            return int(raw_user_id)
        except (TypeError, ValueError):
            return None

    async def _scalar_one_or_none(self, request: Request, stmt):
        session = request.state.session
        if isinstance(session, AsyncSession):
            return (await session.execute(stmt)).scalar_one_or_none()
        result = await anyio.to_thread.run_sync(session.execute, stmt)  # type: ignore[arg-type]
        return result.scalar_one_or_none()

    async def _scalars_all(self, request: Request, stmt) -> list[Any]:
        session = request.state.session
        if isinstance(session, AsyncSession):
            return list((await session.execute(stmt)).scalars().all())
        result = await anyio.to_thread.run_sync(session.execute, stmt)  # type: ignore[arg-type]
        return list(result.scalars().all())

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _extract_foreign_id(
        self,
        data: dict[str, Any],
        *,
        id_field: str,
        relation_field: str,
    ) -> tuple[int | None, str | None]:
        raw_id = data.get(id_field)
        if raw_id not in (None, ""):
            value = self._to_int_or_none(raw_id)
            if value is None:
                return None, "Must be an integer"
            return value, None

        raw_rel = data.get(relation_field)
        if raw_rel in (None, ""):
            return None, None

        if isinstance(raw_rel, dict):
            candidate = raw_rel.get("id")
            value = self._to_int_or_none(candidate)
            if value is None:
                return None, "Must reference a valid id"
            return value, None

        if hasattr(raw_rel, "id"):
            value = self._to_int_or_none(getattr(raw_rel, "id", None))
            if value is None:
                return None, "Must reference a valid id"
            return value, None

        value = self._to_int_or_none(raw_rel)
        if value is None:
            return None, "Must reference a valid id"
        return value, None

    def _extract_foreign_ids(
        self,
        data: dict[str, Any],
        *,
        id_field: str,
        relation_field: str,
    ) -> tuple[list[int], str | None]:
        source = data.get(id_field)
        if source in (None, ""):
            source = data.get(relation_field)

        if source in (None, ""):
            return [], None

        raw_items: list[Any]
        if isinstance(source, str):
            raw_items = [chunk.strip() for chunk in source.split(",") if chunk.strip()]
        elif isinstance(source, (list, tuple, set)):
            raw_items = list(source)
        else:
            raw_items = [source]

        ids: list[int] = []
        for raw_item in raw_items:
            candidate: Any = raw_item
            if isinstance(raw_item, dict):
                candidate = raw_item.get("id")
            elif hasattr(raw_item, "id"):
                candidate = getattr(raw_item, "id", None)

            value = self._to_int_or_none(candidate)
            if value is None:
                return [], "Must reference valid ids"
            ids.append(value)

        # Preserve order, drop duplicates.
        deduped_ids: list[int] = []
        seen: set[int] = set()
        for value in ids:
            if value not in seen:
                seen.add(value)
                deduped_ids.append(value)
        return deduped_ids, None

    @staticmethod
    def _to_datetime_or_none(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                return None
        return None

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

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        del data, obj
        self._audit(request, "before_create")

    async def after_create(self, request: Request, obj: Any) -> None:
        self._audit(request, "after_create", obj)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        del data
        self._audit(request, "before_edit", obj)

    async def after_edit(self, request: Request, obj: Any) -> None:
        self._audit(request, "after_edit", obj)

    async def before_delete(self, request: Request, obj: Any) -> None:
        self._audit(request, "before_delete", obj)

    async def after_delete(self, request: Request, obj: Any) -> None:
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

    def _validate_required_int_min(
        self,
        data: dict[str, Any],
        field: str,
        errors: dict[str, list[str]],
        *,
        minimum: int = 1,
    ) -> None:
        raw_value = data.get(field)
        if raw_value in (None, ""):
            errors.setdefault(field, []).append("Field is required")
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

    async def _validate_existing_fk(
        self,
        request: Request | None,
        *,
        model: Any,
        model_id: int | None,
        errors: dict[str, list[str]],
        field: str,
        message: str = "Must reference an existing record",
    ) -> None:
        if request is None or model_id is None:
            return
        stmt = select(model.id).where(model.id == model_id)
        if await self._scalar_one_or_none(request, stmt) is None:
            errors.setdefault(field, []).append(message)


class TeacherAccessibleModelView(AdminAuditedModelView):
    def _teacher_id(self, request: Request) -> int:
        user_id = self._resolve_admin_user_id(request)
        if user_id is None:
            raise FormValidationError({"_schema": ["Unable to resolve teacher identity"]})
        return user_id

    def is_accessible(self, request: Request) -> bool:
        return self._is_admin(request) or self._is_teacher(request)

    def can_create(self, request: Request) -> bool:
        return self._is_admin(request) or self._is_teacher(request)

    def can_edit(self, request: Request) -> bool:
        return self._is_admin(request) or self._is_teacher(request)

    def can_delete(self, request: Request) -> bool:
        return self._is_admin(request) or self._is_teacher(request)


class TeacherOwnedByFieldModelView(TeacherAccessibleModelView):
    owner_field: str = ""

    def _filter_by_owner(self, request: Request, stmt):
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            owner_column = getattr(self.model, self.owner_field)
            stmt = stmt.where(owner_column == teacher_id)
        return stmt

    def get_list_query(self, request: Request):
        stmt = super().get_list_query(request)
        return self._filter_by_owner(request, stmt)

    def get_details_query(self, request: Request):
        stmt = super().get_details_query(request)
        return self._filter_by_owner(request, stmt)

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if self._is_teacher(request):
            data[self.owner_field] = self._teacher_id(request)
        await super().before_create(request, data, obj)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if self._is_teacher(request):
            if int(getattr(obj, self.owner_field)) != self._teacher_id(request):
                raise FormValidationError({"_schema": ["Insufficient permissions"]})
            data[self.owner_field] = self._teacher_id(request)
        await super().before_edit(request, data, obj)

    async def before_delete(self, request: Request, obj: Any) -> None:
        if self._is_teacher(request):
            if int(getattr(obj, self.owner_field)) != self._teacher_id(request):
                raise FormValidationError({"_schema": ["Insufficient permissions"]})
        await super().before_delete(request, obj)


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

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
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

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request, data
        return None


class MaterialAdminView(TeacherOwnedByFieldModelView):
    name = "Materials"
    icon = "fa fa-book"
    owner_field = "author_id"
    fields = [
        "id",
        "title",
        "material_type",
        "status",
        "description",
        "published_at",
        "author_id",
        "required_level",
    ]
    searchable_fields = ["title", "description"]
    sortable_fields = ["id", "title", "material_type", "status", "published_at", "author_id", "required_level_id"]

    async def _invalidate_material_related_caches(self) -> None:
        try:
            await bump_cache_namespace(NS_MATERIALS, NS_TESTS, NS_TEST_CONTENT)
        except Exception:
            logger.exception("admin_cache_invalidate_failed model=Material")

    async def after_create(self, request: Request, obj: Any) -> None:
        await super().after_create(request, obj)
        await self._invalidate_material_related_caches()

    async def after_edit(self, request: Request, obj: Any) -> None:
        await super().after_edit(request, obj)
        await self._invalidate_material_related_caches()

    async def after_delete(self, request: Request, obj: Any) -> None:
        await super().after_delete(request, obj)
        await self._invalidate_material_related_caches()

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "title", errors, max_len=300)
        material_type = data.get("material_type")
        if material_type not in {"lesson", "module", "article"}:
            errors.setdefault("material_type", []).append("Must be one of: lesson, module, article")
        status = data.get("status")
        if status not in {"draft", "published", "archived"}:
            errors.setdefault("status", []).append("Must be one of: draft, published, archived")
        required_level_id, required_level_id_error = self._extract_foreign_id(
            data,
            id_field="required_level_id",
            relation_field="required_level",
        )
        if required_level_id_error is not None:
            errors.setdefault("required_level", []).append(required_level_id_error)
        elif required_level_id is not None and required_level_id < 1:
            errors.setdefault("required_level", []).append("Must reference ids >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=Level,
                model_id=required_level_id,
                errors=errors,
                field="required_level",
                message="Must reference an existing level",
            )
        raw_author_id = data.get("author_id")
        if raw_author_id not in (None, ""):
            author_id = self._to_int_or_none(raw_author_id)
            if author_id is None:
                errors.setdefault("author_id", []).append("Must be an integer")
            elif author_id < 1:
                errors.setdefault("author_id", []).append("Must be >= 1")
            else:
                await self._validate_existing_fk(
                    request,
                    model=User,
                    model_id=author_id,
                    errors=errors,
                    field="author_id",
                    message="Must reference an existing author",
                )
                if request is not None and self._is_teacher(request) and author_id != self._teacher_id(request):
                    errors.setdefault("author_id", []).append("Teacher can set only own author id")
        if errors:
            raise FormValidationError(errors)


class TestAdminView(TeacherOwnedByFieldModelView):
    name = "Tests"
    icon = "fa fa-file-lines"
    owner_field = "author_id"
    fields = [
        "id",
        "title",
        "description",
        "time_limit_minutes",
        "max_score",
        "max_attempts",
        "published",
        "published_at",
        "materials",
        "deadline",
        "author_id",
        "required_level",
    ]
    searchable_fields = ["title", "description"]
    sortable_fields = [
        "id",
        "title",
        "time_limit_minutes",
        "max_score",
        "max_attempts",
        "published",
        "published_at",
        "author_id",
        "required_level_id",
        "deadline",
    ]

    async def _invalidate_test_related_caches(self) -> None:
        try:
            await bump_cache_namespace(NS_TESTS, NS_TEST_CONTENT, NS_TEST_SUMMARY, NS_MATERIALS)
        except Exception:
            logger.exception("admin_cache_invalidate_failed model=Test")

    async def after_create(self, request: Request, obj: Any) -> None:
        await super().after_create(request, obj)
        await self._invalidate_test_related_caches()

    async def after_edit(self, request: Request, obj: Any) -> None:
        await super().after_edit(request, obj)
        await self._invalidate_test_related_caches()

    async def after_delete(self, request: Request, obj: Any) -> None:
        await super().after_delete(request, obj)
        await self._invalidate_test_related_caches()

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "title", errors, max_len=300)
        self._validate_optional_int_min(data, "time_limit_minutes", errors, minimum=1)
        self._validate_optional_float_min(data, "max_score", errors, minimum=0.0)
        self._validate_optional_int_min(data, "max_attempts", errors, minimum=1)
        required_level_id, required_level_id_error = self._extract_foreign_id(
            data,
            id_field="required_level_id",
            relation_field="required_level",
        )
        if required_level_id_error is not None:
            errors.setdefault("required_level", []).append(required_level_id_error)
        elif required_level_id is not None and required_level_id < 1:
            errors.setdefault("required_level", []).append("Must reference ids >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=Level,
                model_id=required_level_id,
                errors=errors,
                field="required_level",
                message="Must reference an existing level",
            )
        raw_author_id = data.get("author_id")
        if raw_author_id not in (None, ""):
            author_id = self._to_int_or_none(raw_author_id)
            if author_id is None:
                errors.setdefault("author_id", []).append("Must be an integer")
            elif author_id < 1:
                errors.setdefault("author_id", []).append("Must be >= 1")
            else:
                await self._validate_existing_fk(
                    request,
                    model=User,
                    model_id=author_id,
                    errors=errors,
                    field="author_id",
                    message="Must reference an existing author",
                )
                if request is not None and self._is_teacher(request) and author_id != self._teacher_id(request):
                    errors.setdefault("author_id", []).append("Teacher can set only own author id")

        material_ids, material_ids_error = self._extract_foreign_ids(
            data,
            id_field="material_ids",
            relation_field="materials",
        )
        if material_ids_error is not None:
            errors.setdefault("materials", []).append(material_ids_error)
        elif any(material_id < 1 for material_id in material_ids):
            errors.setdefault("materials", []).append("Must reference ids >= 1")
        elif request is not None and material_ids:
            existing_material_ids = set(
                await self._scalars_all(
                    request,
                    select(Material.id).where(Material.id.in_(material_ids)),
                )
            )
            missing_material_ids = set(material_ids) - existing_material_ids
            if missing_material_ids:
                errors.setdefault("materials", []).append("Must reference existing materials")

        if request is not None and self._is_teacher(request) and material_ids:
            teacher_id = self._teacher_id(request)
            owned_material_ids = set(
                (
                    await self._scalars_all(
                        request,
                        select(Material.id).where(Material.id.in_(material_ids), Material.author_id == teacher_id),
                    )
                )
            )
            if len(owned_material_ids) != len(set(material_ids)):
                errors.setdefault("materials", []).append("Teacher can link only own materials")
        if errors:
            raise FormValidationError(errors)


class QuestionAdminView(TeacherAccessibleModelView):
    name = "Questions"
    icon = "fa fa-circle-question"
    fields = ["id", "test", "text", "points", "is_open_answer", "material_urls"]
    searchable_fields = ["text"]
    sortable_fields = ["id", "test_id", "points", "is_open_answer"]
    fields_default_sort = ["test_id asc", "id asc"]

    def get_list_query(self, request: Request):
        stmt = super().get_list_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = stmt.join(Test, Question.test_id == Test.id).where(Test.author_id == teacher_id)
        return stmt

    def get_details_query(self, request: Request):
        stmt = super().get_details_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = stmt.join(Test, Question.test_id == Test.id).where(Test.author_id == teacher_id)
        return stmt

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        test_id, test_id_error = self._extract_foreign_id(data, id_field="test_id", relation_field="test")
        if test_id_error is not None:
            errors.setdefault("test_id", []).append(test_id_error)
        elif test_id is None:
            errors.setdefault("test_id", []).append("Field is required")
        elif test_id < 1:
            errors.setdefault("test_id", []).append("Must be >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=Test,
                model_id=test_id,
                errors=errors,
                field="test_id",
                message="Must reference an existing test",
            )
        self._validate_required_str(data, "text", errors)
        self._validate_optional_float_min(data, "points", errors, minimum=0.0, strict_gt=True)
        if request is not None and self._is_teacher(request) and test_id is not None:
            teacher_id = self._teacher_id(request)
            test_stmt = select(Test.id).where(Test.id == test_id, Test.author_id == teacher_id)
            if await self._scalar_one_or_none(request, test_stmt) is None:
                errors.setdefault("test_id", []).append("Teacher can manage only own tests")
        if errors:
            raise FormValidationError(errors)


class ChoiceAdminView(TeacherAccessibleModelView):
    name = "Choices"
    icon = "fa fa-list"
    fields = ["id", "question", "value", "ordinal", "is_correct"]
    searchable_fields = ["value"]
    sortable_fields = ["id", "question_id", "ordinal", "is_correct"]
    fields_default_sort = ["question_id asc", "ordinal asc", "id asc"]

    def get_list_query(self, request: Request):
        stmt = super().get_list_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = (
                stmt.join(Question, Choice.question_id == Question.id)
                .join(Test, Question.test_id == Test.id)
                .where(Test.author_id == teacher_id)
            )
        return stmt

    def get_details_query(self, request: Request):
        stmt = super().get_details_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = (
                stmt.join(Question, Choice.question_id == Question.id)
                .join(Test, Question.test_id == Test.id)
                .where(Test.author_id == teacher_id)
            )
        return stmt

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        question_id, question_id_error = self._extract_foreign_id(
            data,
            id_field="question_id",
            relation_field="question",
        )
        if question_id_error is not None:
            errors.setdefault("question_id", []).append(question_id_error)
        elif question_id is None:
            errors.setdefault("question_id", []).append("Field is required")
        elif question_id < 1:
            errors.setdefault("question_id", []).append("Must be >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=Question,
                model_id=question_id,
                errors=errors,
                field="question_id",
                message="Must reference an existing question",
            )
        self._validate_required_str(data, "value", errors, max_len=1000)
        self._validate_optional_int_min(data, "ordinal", errors, minimum=0)
        if request is not None and self._is_teacher(request) and question_id is not None:
            teacher_id = self._teacher_id(request)
            question_stmt = (
                select(Question.id)
                .join(Test, Question.test_id == Test.id)
                .where(Question.id == question_id, Test.author_id == teacher_id)
            )
            if await self._scalar_one_or_none(request, question_stmt) is None:
                errors.setdefault("question_id", []).append("Teacher can manage only questions from own tests")
        if errors:
            raise FormValidationError(errors)


class MaterialBlockAdminView(TeacherAccessibleModelView):
    name = "Material Blocks"
    icon = "fa fa-layer-group"
    fields = ["id", "material", "block_type", "title", "body", "url", "order_index"]
    searchable_fields = ["title", "body", "url", "block_type"]
    sortable_fields = ["id", "material_id", "block_type", "order_index"]
    fields_default_sort = ["material_id asc", "order_index asc", "id asc"]

    def get_list_query(self, request: Request):
        stmt = super().get_list_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = stmt.join(Material, MaterialBlock.material_id == Material.id).where(Material.author_id == teacher_id)
        return stmt

    def get_details_query(self, request: Request):
        stmt = super().get_details_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = stmt.join(Material, MaterialBlock.material_id == Material.id).where(Material.author_id == teacher_id)
        return stmt

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        material_id, material_id_error = self._extract_foreign_id(
            data,
            id_field="material_id",
            relation_field="material",
        )
        if material_id_error is not None:
            errors.setdefault("material_id", []).append(material_id_error)
        elif material_id is None:
            errors.setdefault("material_id", []).append("Field is required")
        elif material_id < 1:
            errors.setdefault("material_id", []).append("Must be >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=Material,
                model_id=material_id,
                errors=errors,
                field="material_id",
                message="Must reference an existing material",
            )
        block_type = data.get("block_type")
        if block_type not in MATERIAL_BLOCK_TYPE_VALUES_SET:
            errors.setdefault("block_type", []).append(
                f"Must be one of: {', '.join(MATERIAL_BLOCK_TYPE_VALUES)}"
            )
        self._validate_optional_int_min(data, "order_index", errors, minimum=0)
        if request is not None and self._is_teacher(request) and material_id is not None:
            teacher_id = self._teacher_id(request)
            material_stmt = select(Material.id).where(Material.id == material_id, Material.author_id == teacher_id)
            if await self._scalar_one_or_none(request, material_stmt) is None:
                errors.setdefault("material_id", []).append("Teacher can manage blocks only for own materials")
        if errors:
            raise FormValidationError(errors)


class MaterialAttachmentAdminView(TeacherAccessibleModelView):
    name = "Material Attachments"
    icon = "fa fa-paperclip"
    fields = ["id", "material", "title", "file_url", "file_kind", "order_index", "is_downloadable"]
    searchable_fields = ["title", "file_url", "file_kind"]
    sortable_fields = ["id", "material_id", "file_kind", "order_index", "is_downloadable"]
    fields_default_sort = ["material_id asc", "order_index asc", "id asc"]

    def get_list_query(self, request: Request):
        stmt = super().get_list_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = (
                stmt.join(Material, MaterialAttachment.material_id == Material.id)
                .where(Material.author_id == teacher_id)
            )
        return stmt

    def get_details_query(self, request: Request):
        stmt = super().get_details_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = (
                stmt.join(Material, MaterialAttachment.material_id == Material.id)
                .where(Material.author_id == teacher_id)
            )
        return stmt

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        material_id, material_id_error = self._extract_foreign_id(
            data,
            id_field="material_id",
            relation_field="material",
        )
        if material_id_error is not None:
            errors.setdefault("material_id", []).append(material_id_error)
        elif material_id is None:
            errors.setdefault("material_id", []).append("Field is required")
        elif material_id < 1:
            errors.setdefault("material_id", []).append("Must be >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=Material,
                model_id=material_id,
                errors=errors,
                field="material_id",
                message="Must reference an existing material",
            )
        self._validate_required_str(data, "title", errors, max_len=300)
        self._validate_required_str(data, "file_url", errors, max_len=1000)
        file_kind = data.get("file_kind")
        if file_kind not in MATERIAL_ATTACHMENT_KIND_VALUES_SET:
            errors.setdefault("file_kind", []).append(
                f"Must be one of: {', '.join(MATERIAL_ATTACHMENT_KIND_VALUES)}"
            )
        self._validate_optional_int_min(data, "order_index", errors, minimum=0)
        if request is not None and self._is_teacher(request) and material_id is not None:
            teacher_id = self._teacher_id(request)
            material_stmt = select(Material.id).where(Material.id == material_id, Material.author_id == teacher_id)
            if await self._scalar_one_or_none(request, material_stmt) is None:
                errors.setdefault("material_id", []).append("Teacher can manage attachments only for own materials")
        if errors:
            raise FormValidationError(errors)


class LevelAdminView(AdminAuditedModelView):
    name = "Levels"
    icon = "fa fa-signal"
    fields = ["id", "name", "required_points", "description"]
    searchable_fields = ["name", "description"]
    sortable_fields = ["id", "name", "required_points"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "name", errors, max_len=200)
        self._validate_optional_int_min(data, "required_points", errors, minimum=0)
        if errors:
            raise FormValidationError(errors)


class StudyGroupAdminView(TeacherOwnedByFieldModelView):
    name = "Study Groups"
    icon = "fa fa-users-rectangle"
    owner_field = "teacher_id"
    fields = ["id", "name", "teacher"]
    searchable_fields = ["name"]
    sortable_fields = ["id", "name", "teacher_id"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request
        errors: dict[str, list[str]] = {}
        self._validate_required_str(data, "name", errors, max_len=200)
        if errors:
            raise FormValidationError(errors)


class GroupMembershipAdminView(TeacherAccessibleModelView):
    name = "Group Memberships"
    icon = "fa fa-user-group"
    fields = ["id", "group", "user"]
    sortable_fields = ["id", "group_id", "user_id"]
    fields_default_sort = ["group_id asc", "id asc"]

    def get_list_query(self, request: Request):
        stmt = super().get_list_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = stmt.join(StudyGroup, GroupMembership.group_id == StudyGroup.id).where(StudyGroup.teacher_id == teacher_id)
        return stmt

    def get_details_query(self, request: Request):
        stmt = super().get_details_query(request)
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            stmt = stmt.join(StudyGroup, GroupMembership.group_id == StudyGroup.id).where(StudyGroup.teacher_id == teacher_id)
        return stmt

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        errors: dict[str, list[str]] = {}
        group_id, group_id_error = self._extract_foreign_id(data, id_field="group_id", relation_field="group")
        if group_id_error is not None:
            errors.setdefault("group_id", []).append(group_id_error)
        elif group_id is None:
            errors.setdefault("group_id", []).append("Field is required")
        elif group_id < 1:
            errors.setdefault("group_id", []).append("Must be >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=StudyGroup,
                model_id=group_id,
                errors=errors,
                field="group_id",
                message="Must reference an existing group",
            )

        user_id, user_id_error = self._extract_foreign_id(data, id_field="user_id", relation_field="user")
        if user_id_error is not None:
            errors.setdefault("user_id", []).append(user_id_error)
        elif user_id is None:
            errors.setdefault("user_id", []).append("Field is required")
        elif user_id < 1:
            errors.setdefault("user_id", []).append("Must be >= 1")
        else:
            await self._validate_existing_fk(
                request,
                model=User,
                model_id=user_id,
                errors=errors,
                field="user_id",
                message="Must reference an existing user",
            )

        if request is not None and self._is_teacher(request) and group_id is not None:
            teacher_id = self._teacher_id(request)
            group_stmt = select(StudyGroup.id).where(StudyGroup.id == group_id, StudyGroup.teacher_id == teacher_id)
            if await self._scalar_one_or_none(request, group_stmt) is None:
                errors.setdefault("group_id", []).append("Teacher can manage memberships only for own groups")
        if errors:
            raise FormValidationError(errors)


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


def get_admin_views() -> list[ModelView]:
    return [
        UserReadOnlyView(User),
        LevelAdminView(Level),
        MaterialAdminView(Material),
        MaterialBlockAdminView(MaterialBlock),
        MaterialAttachmentAdminView(MaterialAttachment),
        TestAdminView(Test),
        QuestionAdminView(Question),
        ChoiceAdminView(Choice),
        StudyGroupAdminView(StudyGroup),
        GroupMembershipAdminView(GroupMembership),
        AnalyticsReadOnlyView(Analytics),
        TestAttemptReadOnlyView(TestAttempt),
        AnswerReadOnlyView(Answer),
        PointsLedgerReadOnlyView(PointsLedger),
        UserAchievementReadOnlyView(UserAchievement),
        UserRewardReadOnlyView(UserReward),
        AchievementDefinitionAdminView(AchievementDefinition),
        RewardDefinitionAdminView(RewardDefinition),
        UnlockRuleAdminView(UnlockRule),
        ChallengeAdminView(Challenge),
        UserChallengeProgressReadOnlyView(UserChallengeProgress),
        UserChallengeClaimReadOnlyView(UserChallengeClaim),
        AIGamificationJobReadOnlyView(AIGamificationJob),
        SeasonAdminView(Season),
        LeaderboardSnapshotReadOnlyView(LeaderboardSnapshot),
    ]

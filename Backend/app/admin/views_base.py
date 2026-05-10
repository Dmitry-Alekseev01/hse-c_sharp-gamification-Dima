import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.models.test_ import Test

logger = logging.getLogger(__name__)


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
        # Admin is configured with a synchronous SQLAlchemy engine.
        # Keep sync-session calls on the same thread to avoid session cross-thread hazards.
        result = session.execute(stmt)  # type: ignore[call-arg]
        return result.scalar_one_or_none()

    async def _scalars_all(self, request: Request, stmt) -> list[Any]:
        session = request.state.session
        if isinstance(session, AsyncSession):
            return list((await session.execute(stmt)).scalars().all())
        result = session.execute(stmt)  # type: ignore[call-arg]
        return list(result.scalars().all())

    async def _commit_session(self, request: Request) -> None:
        session = request.state.session
        if isinstance(session, AsyncSession):
            await session.commit()
            return
        session.commit()  # type: ignore[call-arg]

    async def _rollback_session(self, request: Request) -> None:
        session = request.state.session
        if isinstance(session, AsyncSession):
            await session.rollback()
            return
        session.rollback()  # type: ignore[call-arg]

    @staticmethod
    def _humanize_action_error(exc: Exception) -> str:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        text = str(exc).strip()
        return text or "Operation failed"

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


class TeacherScopedByTestReadOnlyView(TeacherAccessibleModelView):
    row_actions = ["view"]
    test_id_field: str = "test_id"

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return False

    def _scope_to_teacher_tests(self, request: Request, stmt):
        if self._is_teacher(request):
            teacher_id = self._teacher_id(request)
            test_ids_stmt = select(Test.id).where(Test.author_id == teacher_id)
            test_id_column = getattr(self.model, self.test_id_field)
            stmt = stmt.where(test_id_column.in_(test_ids_stmt))
        return stmt

    def get_list_query(self, request: Request):
        stmt = super().get_list_query(request)
        return self._scope_to_teacher_tests(request, stmt)

    def get_details_query(self, request: Request):
        stmt = super().get_details_query(request)
        return self._scope_to_teacher_tests(request, stmt)

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        del request, data
        return None

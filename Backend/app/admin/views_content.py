import logging
from typing import Any

from sqlalchemy import select
from starlette.requests import Request
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import EnumField

from app.cache.redis_cache import NS_MATERIALS, NS_TEST_CONTENT, NS_TEST_SUMMARY, NS_TESTS, bump_cache_namespace
from app.core.material_taxonomy import MATERIAL_ATTACHMENT_KIND_VALUES, MATERIAL_BLOCK_TYPE_VALUES
from app.models.choice import Choice
from app.models.group import GroupMembership, StudyGroup
from app.models.level import Level
from app.models.material import Material
from app.models.material_attachment import MaterialAttachment
from app.models.material_block import MaterialBlock
from app.models.question import Question
from app.models.test_ import Test
from app.models.user import User

from .views_base import AdminAuditedModelView, TeacherAccessibleModelView, TeacherOwnedByFieldModelView

logger = logging.getLogger(__name__)
MATERIAL_BLOCK_TYPE_VALUES_SET = set(MATERIAL_BLOCK_TYPE_VALUES)
MATERIAL_ATTACHMENT_KIND_VALUES_SET = set(MATERIAL_ATTACHMENT_KIND_VALUES)
MATERIAL_TYPE_CHOICES = [("lesson", "lesson"), ("module", "module"), ("article", "article")]
MATERIAL_STATUS_CHOICES = [("draft", "draft"), ("published", "published"), ("archived", "archived")]
MATERIAL_BLOCK_TYPE_CHOICES = [(value, value) for value in MATERIAL_BLOCK_TYPE_VALUES]


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
        EnumField("material_type", choices=MATERIAL_TYPE_CHOICES, required=True),
        EnumField("status", choices=MATERIAL_STATUS_CHOICES, required=True),
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
    fields = [
        "id",
        "material",
        EnumField("block_type", choices=MATERIAL_BLOCK_TYPE_CHOICES, required=True),
        "title",
        "body",
        "url",
        "order_index",
    ]
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

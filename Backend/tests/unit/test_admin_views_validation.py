import pytest
from starlette_admin.exceptions import FormValidationError

from app.admin.views import ChoiceAdminView, QuestionAdminView
from app.models.choice import Choice
from app.models.question import Question

pytestmark = pytest.mark.asyncio


async def test_question_admin_view_validate_rejects_missing_test_id():
    view = QuestionAdminView(Question)

    with pytest.raises(FormValidationError):
        await view.validate(None, {"text": "What is C#?", "points": 1.0})


async def test_question_admin_view_validate_accepts_valid_payload():
    view = QuestionAdminView(Question)

    await view.validate(None, {"test_id": 1, "text": "What is C#?", "points": 1.0})


async def test_choice_admin_view_validate_rejects_missing_question_id():
    view = ChoiceAdminView(Choice)

    with pytest.raises(FormValidationError):
        await view.validate(None, {"value": "CLR", "ordinal": 1, "is_correct": True})


async def test_choice_admin_view_validate_accepts_valid_payload():
    view = ChoiceAdminView(Choice)

    await view.validate(None, {"question_id": 1, "value": "CLR", "ordinal": 1, "is_correct": True})

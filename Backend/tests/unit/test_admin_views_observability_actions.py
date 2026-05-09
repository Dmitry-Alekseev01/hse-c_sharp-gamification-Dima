from types import SimpleNamespace

import pytest

from app.admin.views_observability import AnswerReadOnlyView, TestAttemptReadOnlyView as _TestAttemptReadOnlyView
from app.models.answer import Answer
from app.models.test_attempt import TestAttempt as _TestAttempt

pytestmark = pytest.mark.asyncio


class _DummyActionRequest:
    def __init__(self, *, form_data: dict[str, str], user_id: int = 1):
        self.session = {
            "admin_role": "admin",
            "admin_user_id": user_id,
            "admin_username": f"admin{user_id}@example.com",
        }
        self.state = SimpleNamespace(
            admin_user=SimpleNamespace(id=user_id, username=f"admin{user_id}@example.com"),
            session=object(),
        )
        self._form_data = form_data

    async def form(self):
        return self._form_data


class _FakeAsyncSessionCtx:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


async def test_test_attempt_row_action_uses_dedicated_async_session(monkeypatch):
    request = _DummyActionRequest(form_data={"score": "4.5"}, user_id=101)
    fake_ctx = _FakeAsyncSessionCtx()
    captured: dict[str, object] = {}

    async def _fake_find_by_pk(req, pk):
        del req, pk
        return SimpleNamespace(id=7, test_id=2, status="completed", max_score=None)

    async def _fake_get_attempt(session, attempt_id: int):
        captured["get_attempt_session"] = session
        captured["attempt_id"] = attempt_id
        return SimpleNamespace(id=7, user_id=55, status="completed", max_score=None)

    async def _fake_refresh_attempt_scores(session, attempt):
        captured["refresh_session"] = session
        attempt.max_score = 10.0
        return attempt

    async def _fake_set_manual_score(session, attempt, score: float):
        captured["set_score_session"] = session
        captured["score"] = score
        attempt.manual_score = score
        return attempt

    async def _fake_bump_attempts(user_id: int):
        captured["bump_attempts_user_id"] = user_id

    async def _fake_bump_cache(*namespaces):
        captured["bump_cache_namespaces"] = namespaces

    monkeypatch.setattr("app.admin.views_observability.AsyncSessionLocal", lambda: fake_ctx)
    monkeypatch.setattr("app.admin.views_observability.test_attempt_repo.get_attempt", _fake_get_attempt)
    monkeypatch.setattr("app.admin.views_observability.test_attempt_repo.refresh_attempt_scores", _fake_refresh_attempt_scores)
    monkeypatch.setattr("app.admin.views_observability.test_attempt_repo.set_manual_score", _fake_set_manual_score)
    monkeypatch.setattr("app.admin.views_observability.bump_user_attempts_state_version", _fake_bump_attempts)
    monkeypatch.setattr("app.admin.views_observability.bump_cache_namespace", _fake_bump_cache)

    view = _TestAttemptReadOnlyView(_TestAttempt)
    monkeypatch.setattr(view, "find_by_pk", _fake_find_by_pk)

    message = await view.set_manual_score_row_action(request, pk="7")

    assert message == "Manual score updated for attempt #7"
    assert fake_ctx.committed is True
    assert fake_ctx.rolled_back is False
    assert captured["get_attempt_session"] is fake_ctx
    assert captured["refresh_session"] is fake_ctx
    assert captured["set_score_session"] is fake_ctx
    assert captured["score"] == 4.5
    assert captured["attempt_id"] == 7
    assert captured["bump_attempts_user_id"] == 55
    assert captured["bump_cache_namespaces"] == ("test_summary",)


async def test_answer_row_action_uses_dedicated_async_session(monkeypatch):
    request = _DummyActionRequest(form_data={"score": "3.25"}, user_id=202)
    fake_ctx = _FakeAsyncSessionCtx()
    captured: dict[str, object] = {}

    async def _fake_find_by_pk(req, pk):
        del req, pk
        return SimpleNamespace(id=11, test_id=3)

    async def _fake_manual_grade(session, *, answer_id: int, grader_id: int, score: float):
        captured["session"] = session
        captured["answer_id"] = answer_id
        captured["grader_id"] = grader_id
        captured["score"] = score

    monkeypatch.setattr("app.admin.views_observability.AsyncSessionLocal", lambda: fake_ctx)
    monkeypatch.setattr("app.admin.views_observability.manual_grade_open_answer_service", _fake_manual_grade)

    view = AnswerReadOnlyView(Answer)
    monkeypatch.setattr(view, "find_by_pk", _fake_find_by_pk)

    message = await view.grade_answer_row_action(request, pk="11")

    assert message == "Answer #11 was graded successfully"
    assert fake_ctx.committed is True
    assert fake_ctx.rolled_back is False
    assert captured["session"] is fake_ctx
    assert captured["answer_id"] == 11
    assert captured["grader_id"] == 202
    assert captured["score"] == 3.25

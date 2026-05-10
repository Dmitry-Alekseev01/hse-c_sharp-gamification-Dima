from types import SimpleNamespace

import pytest

from app.admin.views_base import AdminAuditedModelView
from app.models.level import Level

pytestmark = pytest.mark.asyncio


class _FakeResult:
    def __init__(self, scalar_value=None, many_values=None):
        self._scalar_value = scalar_value
        self._many_values = list(many_values or [])

    def scalar_one_or_none(self):
        return self._scalar_value

    def scalars(self):
        return self

    def all(self):
        return list(self._many_values)


class _FakeSyncSession:
    def __init__(self, *, scalar_value=None, many_values=None):
        self._scalar_value = scalar_value
        self._many_values = list(many_values or [])
        self.execute_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, stmt):
        del stmt
        self.execute_calls += 1
        return _FakeResult(scalar_value=self._scalar_value, many_values=self._many_values)

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1


def _request_with_session(session):
    return SimpleNamespace(
        session={"admin_role": "admin"},
        state=SimpleNamespace(session=session),
    )


async def test_admin_view_scalar_helpers_work_with_sync_session():
    view = AdminAuditedModelView(Level)
    sync_session = _FakeSyncSession(scalar_value=123, many_values=[1, 2, 3])
    request = _request_with_session(sync_session)

    scalar_value = await view._scalar_one_or_none(request, stmt=object())
    many_values = await view._scalars_all(request, stmt=object())

    assert scalar_value == 123
    assert many_values == [1, 2, 3]
    assert sync_session.execute_calls == 2


async def test_admin_view_commit_and_rollback_work_with_sync_session():
    view = AdminAuditedModelView(Level)
    sync_session = _FakeSyncSession()
    request = _request_with_session(sync_session)

    await view._commit_session(request)
    await view._rollback_session(request)

    assert sync_session.commit_calls == 1
    assert sync_session.rollback_calls == 1

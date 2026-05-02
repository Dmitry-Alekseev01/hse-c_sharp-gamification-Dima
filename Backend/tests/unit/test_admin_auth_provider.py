from types import SimpleNamespace

import pytest
from starlette.responses import Response
from starlette_admin.exceptions import LoginFailed

from app.admin.auth_provider import AdminOnlyAuthProvider
from app.admin.mfa import verify_totp_code
from app.core.config import settings

pytestmark = pytest.mark.asyncio


class _DummySessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


class _DummyRequest:
    def __init__(self):
        self.session: dict = {}
        self.state = SimpleNamespace()
        self.headers: dict = {}
        self.client = SimpleNamespace(host="127.0.0.1")

    async def form(self):
        return {}


class _FakeRedis:
    def __init__(self):
        self._values: dict[str, int | str] = {}

    async def ttl(self, key: str) -> int:
        if key in self._values:
            return 60
        return -2

    async def ping(self) -> bool:
        return True

    async def incr(self, key: str) -> int:
        value = int(self._values.get(key, 0)) + 1
        self._values[key] = value
        return value

    async def expire(self, key: str, seconds: int) -> bool:
        del key, seconds
        return True

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        del ex
        self._values[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._values:
                del self._values[key]
                deleted += 1
        return deleted


@pytest.mark.asyncio
async def test_admin_auth_provider_login_allows_admin_only(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    response = Response()

    async def fake_authenticate_user(db, username: str, password: str):
        del db, username, password
        return SimpleNamespace(id=77, username="admin@example.com", role="admin")

    fake_redis = _FakeRedis()
    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.auth_repo.authenticate_user", fake_authenticate_user)
    monkeypatch.setattr("app.admin.auth_provider.get_redis_client", lambda: fake_redis)

    result = await provider.login("admin@example.com", "secret", remember_me=False, request=request, response=response)

    assert result is response
    assert request.session["admin_user_id"] == 77
    assert request.session["admin_username"] == "admin@example.com"
    assert request.session["admin_role"] == "admin"


@pytest.mark.asyncio
async def test_admin_auth_provider_login_allows_teacher(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    response = Response()

    async def fake_authenticate_user(db, username: str, password: str):
        del db, username, password
        return SimpleNamespace(id=5, username="teacher@example.com", role="teacher")

    fake_redis = _FakeRedis()
    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.auth_repo.authenticate_user", fake_authenticate_user)
    monkeypatch.setattr("app.admin.auth_provider.get_redis_client", lambda: fake_redis)

    result = await provider.login("teacher@example.com", "secret", remember_me=False, request=request, response=response)

    assert result is response
    assert request.session["admin_user_id"] == 5
    assert request.session["admin_username"] == "teacher@example.com"
    assert request.session["admin_role"] == "teacher"


@pytest.mark.asyncio
async def test_admin_auth_provider_login_rejects_non_operator(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    response = Response()

    async def fake_authenticate_user(db, username: str, password: str):
        del db, username, password
        return SimpleNamespace(id=5, username="student@example.com", role="user")

    fake_redis = _FakeRedis()
    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.auth_repo.authenticate_user", fake_authenticate_user)
    monkeypatch.setattr("app.admin.auth_provider.get_redis_client", lambda: fake_redis)

    with pytest.raises(LoginFailed):
        await provider.login("student@example.com", "secret", remember_me=False, request=request, response=response)


@pytest.mark.asyncio
async def test_admin_auth_provider_is_authenticated_sets_admin_user(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    request.session.update({"admin_user_id": 10, "admin_username": "admin@example.com", "admin_role": "admin"})

    async def fake_get_user_by_id(db, user_id: int):
        del db
        if user_id == 10:
            return SimpleNamespace(id=10, username="admin@example.com", role="admin")
        return None

    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.user_repo.get_user_by_id", fake_get_user_by_id)

    is_auth = await provider.is_authenticated(request)

    assert is_auth is True
    assert getattr(request.state, "admin_user").username == "admin@example.com"
    admin_user = provider.get_admin_user(request)
    assert admin_user is not None
    assert admin_user.username == "admin@example.com"


@pytest.mark.asyncio
async def test_admin_auth_provider_is_authenticated_clears_invalid_session(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    request.session.update({"admin_user_id": 11, "admin_username": "student@example.com", "admin_role": "user"})

    async def fake_get_user_by_id(db, user_id: int):
        del db, user_id
        return SimpleNamespace(id=11, username="student@example.com", role="user")

    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.user_repo.get_user_by_id", fake_get_user_by_id)

    is_auth = await provider.is_authenticated(request)

    assert is_auth is False
    assert request.session == {}


@pytest.mark.asyncio
async def test_admin_auth_provider_is_authenticated_allows_teacher(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    request.session.update({"admin_user_id": 12, "admin_username": "teacher@example.com", "admin_role": "teacher"})

    async def fake_get_user_by_id(db, user_id: int):
        del db
        if user_id == 12:
            return SimpleNamespace(id=12, username="teacher@example.com", role="teacher")
        return None

    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.user_repo.get_user_by_id", fake_get_user_by_id)

    is_auth = await provider.is_authenticated(request)

    assert is_auth is True
    assert getattr(request.state, "admin_user").username == "teacher@example.com"


@pytest.mark.asyncio
async def test_admin_auth_provider_logout_clears_session():
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    request.session.update({"admin_user_id": 1, "admin_username": "admin@example.com", "admin_role": "admin"})
    response = Response()

    result = await provider.logout(request, response)

    assert result is response
    assert request.session == {}


@pytest.mark.asyncio
async def test_admin_auth_provider_blocks_after_too_many_failed_attempts(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    response = Response()

    async def fake_authenticate_user(db, username: str, password: str):
        del db, username, password
        return None

    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "admin_login_max_attempts", 2)
    monkeypatch.setattr(settings, "admin_login_window_seconds", 300)
    monkeypatch.setattr(settings, "admin_login_block_seconds", 900)
    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.auth_repo.authenticate_user", fake_authenticate_user)
    monkeypatch.setattr("app.admin.auth_provider.get_redis_client", lambda: fake_redis)

    with pytest.raises(LoginFailed):
        await provider.login("admin@example.com", "bad-1", remember_me=False, request=request, response=response)

    with pytest.raises(LoginFailed):
        await provider.login("admin@example.com", "bad-2", remember_me=False, request=request, response=response)

    with pytest.raises(LoginFailed, match="Too many attempts"):
        await provider.login("admin@example.com", "bad-3", remember_me=False, request=request, response=response)


@pytest.mark.asyncio
async def test_admin_auth_provider_login_with_mfa_suffix(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    response = Response()

    secret = "JBSWY3DPEHPK3PXP"
    code = "282760"
    assert verify_totp_code(
        secret=secret,
        code=code,
        period_seconds=30,
        digits=6,
        drift_windows=0,
        now_ts=0,
    )

    async def fake_authenticate_user(db, username: str, password: str):
        del db, username
        assert password == "secret"
        return SimpleNamespace(id=77, username="admin@example.com", role="admin")

    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "admin_mfa_enabled", True)
    monkeypatch.setattr(settings, "admin_mfa_totp_secret", secret)
    monkeypatch.setattr(settings, "admin_mfa_totp_period_seconds", 30)
    monkeypatch.setattr(settings, "admin_mfa_totp_digits", 6)
    monkeypatch.setattr(settings, "admin_mfa_totp_drift_windows", 1)
    monkeypatch.setattr("app.admin.auth_provider.time.time", lambda: 0)
    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.auth_repo.authenticate_user", fake_authenticate_user)
    monkeypatch.setattr("app.admin.auth_provider.get_redis_client", lambda: fake_redis)

    result = await provider.login(
        "admin@example.com",
        f"secret::{code}",
        remember_me=False,
        request=request,
        response=response,
    )

    assert result is response
    assert request.session["admin_user_id"] == 77


@pytest.mark.asyncio
async def test_admin_auth_provider_login_with_mfa_invalid_code(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    response = Response()

    async def fake_authenticate_user(db, username: str, password: str):
        del db, username, password
        return SimpleNamespace(id=77, username="admin@example.com", role="admin")

    fake_redis = _FakeRedis()
    monkeypatch.setattr(settings, "admin_mfa_enabled", True)
    monkeypatch.setattr(settings, "admin_mfa_totp_secret", "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(settings, "admin_mfa_totp_period_seconds", 30)
    monkeypatch.setattr(settings, "admin_mfa_totp_digits", 6)
    monkeypatch.setattr(settings, "admin_mfa_totp_drift_windows", 1)
    monkeypatch.setattr("app.admin.auth_provider.time.time", lambda: 0)
    monkeypatch.setattr("app.admin.auth_provider.AsyncSessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr("app.admin.auth_provider.auth_repo.authenticate_user", fake_authenticate_user)
    monkeypatch.setattr("app.admin.auth_provider.get_redis_client", lambda: fake_redis)

    with pytest.raises(LoginFailed, match="Invalid username or password"):
        await provider.login(
            "admin@example.com",
            "secret::000000",
            remember_me=False,
            request=request,
            response=response,
        )


@pytest.mark.asyncio
async def test_admin_auth_provider_login_is_blocked_when_redis_unavailable(monkeypatch):
    provider = AdminOnlyAuthProvider()
    request = _DummyRequest()
    response = Response()

    class _BrokenRedis:
        async def ping(self):
            raise RuntimeError("redis down")

    monkeypatch.setattr("app.admin.auth_provider.get_redis_client", lambda: _BrokenRedis())

    with pytest.raises(LoginFailed, match="temporarily unavailable"):
        await provider.login(
            "admin@example.com",
            "secret",
            remember_me=False,
            request=request,
            response=response,
        )

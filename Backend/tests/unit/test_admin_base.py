from fastapi import FastAPI
import pytest

from app.admin import admin_base
from app.core.config import settings


def _route_paths(app: FastAPI) -> list[str]:
    return [getattr(route, "path", "") for route in app.routes]


def test_build_sync_database_url_replaces_asyncpg_driver():
    async_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/app_db"
    sync_url = admin_base._build_sync_database_url(async_url)
    assert sync_url == "postgresql+psycopg2://postgres:postgres@localhost:5432/app_db"


def test_build_sync_database_url_replaces_aiosqlite_driver():
    async_url = "sqlite+aiosqlite:///./local.db"
    sync_url = admin_base._build_sync_database_url(async_url)
    assert sync_url == "sqlite:///./local.db"


def test_setup_admin_respects_disabled_flag(monkeypatch):
    monkeypatch.setattr(settings, "admin_enabled", False)
    app = FastAPI()

    admin_base.reset_admin_state_for_tests()
    admin_base.setup_admin(app)

    assert "/admin" not in _route_paths(app)
    admin_base.reset_admin_state_for_tests()


def test_setup_admin_mounts_custom_base_url(monkeypatch):
    monkeypatch.setattr(settings, "admin_enabled", True)
    monkeypatch.setattr(settings, "admin_base_url", "/internal-admin")
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///./test_admin.db")

    app = FastAPI()

    admin_base.reset_admin_state_for_tests()
    admin_base.setup_admin(app)

    assert "/internal-admin" in _route_paths(app)
    admin_base.reset_admin_state_for_tests()


def test_setup_admin_rejects_insecure_production_cookie(monkeypatch):
    monkeypatch.setattr(settings, "admin_enabled", True)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_session_https_only", False)
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///./test_admin.db")

    app = FastAPI()
    admin_base.reset_admin_state_for_tests()

    try:
        with pytest.raises(RuntimeError, match="ADMIN_SESSION_HTTPS_ONLY"):
            admin_base.setup_admin(app)
    finally:
        admin_base.reset_admin_state_for_tests()


def test_setup_admin_rejects_short_secrets_in_production(monkeypatch):
    monkeypatch.setattr(settings, "admin_enabled", True)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_session_https_only", True)
    monkeypatch.setattr(settings, "jwt_secret_key", "short-secret")
    monkeypatch.setattr(settings, "admin_session_secret_key", "short-secret")
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///./test_admin.db")

    app = FastAPI()
    admin_base.reset_admin_state_for_tests()

    try:
        with pytest.raises(RuntimeError, match="at least 32 chars"):
            admin_base.setup_admin(app)
    finally:
        admin_base.reset_admin_state_for_tests()


def test_setup_admin_rejects_invalid_admin_ip_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "admin_enabled", True)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "admin_allowed_ips", "not_an_ip")
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///./test_admin.db")

    app = FastAPI()
    admin_base.reset_admin_state_for_tests()

    try:
        with pytest.raises(ValueError):
            admin_base.setup_admin(app)
    finally:
        admin_base.reset_admin_state_for_tests()


def test_setup_admin_rejects_invalid_mfa_secret_in_production(monkeypatch):
    monkeypatch.setattr(settings, "admin_enabled", True)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_session_https_only", True)
    monkeypatch.setattr(settings, "jwt_secret_key", "x" * 40)
    monkeypatch.setattr(settings, "admin_session_secret_key", "y" * 40)
    monkeypatch.setattr(settings, "admin_mfa_enabled", True)
    monkeypatch.setattr(settings, "admin_mfa_totp_secret", "invalid_secret")
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///./test_admin.db")

    app = FastAPI()
    admin_base.reset_admin_state_for_tests()

    try:
        with pytest.raises(RuntimeError, match="ADMIN_MFA_TOTP_SECRET"):
            admin_base.setup_admin(app)
    finally:
        admin_base.reset_admin_state_for_tests()


def test_setup_admin_rejects_invalid_mfa_secret_in_development(monkeypatch):
    monkeypatch.setattr(settings, "admin_enabled", True)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "admin_mfa_enabled", True)
    monkeypatch.setattr(settings, "admin_mfa_totp_secret", "invalid_secret")
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///./test_admin.db")

    app = FastAPI()
    admin_base.reset_admin_state_for_tests()

    try:
        with pytest.raises(RuntimeError, match="ADMIN_MFA_TOTP_SECRET"):
            admin_base.setup_admin(app)
    finally:
        admin_base.reset_admin_state_for_tests()

import logging

from sqlalchemy import Engine, create_engine
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_admin.contrib.sqla import Admin

from app.admin.mfa import is_valid_totp_secret
from app.admin.auth_provider import AdminOnlyAuthProvider
from app.admin.views import get_admin_views
from app.core.config import settings

_admin_instance: Admin | None = None
_admin_engine: Engine | None = None

logger = logging.getLogger(__name__)


def _build_sync_database_url(async_database_url: str) -> str:
    if async_database_url.startswith("postgresql+asyncpg://"):
        return async_database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if async_database_url.startswith("sqlite+aiosqlite://"):
        return async_database_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return async_database_url


def _build_admin_engine() -> Engine:
    sync_database_url = _build_sync_database_url(settings.get_database_url())
    engine_kwargs: dict = {"future": True}
    if sync_database_url.startswith("sqlite://"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(sync_database_url, **engine_kwargs)


def _ensure_production_admin_security() -> None:
    if settings.app_env.lower() != "production":
        return

    if not settings.admin_session_https_only:
        raise RuntimeError("ADMIN_SESSION_HTTPS_ONLY must be true in production")

    admin_secret = settings.get_admin_session_secret_key()
    jwt_secret = settings.get_jwt_secret_key()
    if len(admin_secret) < 32:
        raise RuntimeError("ADMIN_SESSION_SECRET_KEY (or SECRET_KEY fallback) must be at least 32 chars")
    if len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY (or SECRET_KEY fallback) must be at least 32 chars")


def _ensure_admin_mfa_config() -> None:
    if not settings.admin_mfa_enabled:
        return
    if not is_valid_totp_secret(settings.admin_mfa_totp_secret):
        raise RuntimeError("ADMIN_MFA_TOTP_SECRET is required when ADMIN_MFA_ENABLED=true")
    if settings.admin_mfa_totp_digits <= 0:
        raise RuntimeError("ADMIN_MFA_TOTP_DIGITS must be > 0")
    if settings.admin_mfa_totp_period_seconds <= 0:
        raise RuntimeError("ADMIN_MFA_TOTP_PERIOD_SECONDS must be > 0")
    if settings.admin_mfa_totp_drift_windows < 0:
        raise RuntimeError("ADMIN_MFA_TOTP_DRIFT_WINDOWS must be >= 0")


def setup_admin(app) -> None:
    global _admin_instance, _admin_engine
    if not settings.admin_enabled:
        logger.info("Admin panel is disabled by configuration")
        return

    if _admin_instance is not None:
        return

    _ensure_production_admin_security()
    _ensure_admin_mfa_config()
    # Fail fast on invalid allowlist syntax at startup.
    settings.get_admin_allowed_networks()

    _admin_engine = _build_admin_engine()
    _admin_instance = Admin(
        _admin_engine,
        title="HSE C# Admin",
        base_url=settings.admin_base_url,
        auth_provider=AdminOnlyAuthProvider(),
        middlewares=[
            Middleware(
                SessionMiddleware,
                secret_key=settings.get_admin_session_secret_key(),
                max_age=settings.admin_session_max_age_seconds,
                https_only=settings.admin_session_https_only,
                same_site=settings.get_admin_session_same_site(),
                session_cookie="admin_session",
            )
        ],
    )

    for view in get_admin_views():
        _admin_instance.add_view(view)

    _admin_instance.mount_to(app)


def reset_admin_state_for_tests() -> None:
    global _admin_instance, _admin_engine
    if _admin_engine is not None:
        _admin_engine.dispose()
    _admin_instance = None
    _admin_engine = None

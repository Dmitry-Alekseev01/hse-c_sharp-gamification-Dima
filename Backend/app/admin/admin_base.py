import logging

from sqlalchemy import Engine, create_engine
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_admin.contrib.sqla import Admin

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


def setup_admin(app) -> None:
    global _admin_instance, _admin_engine
    if not settings.admin_enabled:
        logger.info("Admin panel is disabled by configuration")
        return

    if _admin_instance is not None:
        return

    if settings.app_env.lower() == "production" and not settings.admin_session_https_only:
        logger.warning("Admin session cookie is not https-only in production")

    _admin_engine = _build_admin_engine()
    _admin_instance = Admin(
        _admin_engine,
        title="HSE C# Admin",
        base_url=settings.admin_base_url,
        auth_provider=AdminOnlyAuthProvider(),
        middlewares=[
            Middleware(
                SessionMiddleware,
                secret_key=settings.secret_key,
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

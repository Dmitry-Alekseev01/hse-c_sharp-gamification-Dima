# tests/conftest.py
import os, sys
from pathlib import Path
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine, AsyncSession
from httpx import AsyncClient, ASGITransport

# add project root so `import app` работает
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.api.deps import POST_COMMIT_TASKS_KEY, get_db, run_post_commit_tasks
from app.cache import redis_cache
from app.core.config import settings
from app.db.session import Base
from app.main import app

# для CI/локал тестов: по умолчанию sqlite in-memory
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="session")
async def async_engine() -> AsyncEngine:
    engine = create_async_engine(TEST_DATABASE_URL, future=True, echo=False)
    # создаём схему один раз
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


# Алиасы/совместимость с тестами, которые ждут fixture 'engine'
@pytest.fixture(scope="session")
async def engine(async_engine: AsyncEngine) -> AsyncEngine:
    return async_engine


@pytest.fixture()
async def session(async_engine: AsyncEngine) -> AsyncSession:
    """
    Простая per-test сессия. По завершении теста делаем rollback,
    чтобы не сохранять состояние между тестами.
    """
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)
    async with async_session() as s:
        yield s
        # откат: если тест что-то закоммитил, откатим изменения
        try:
            await s.rollback()
        except Exception:
            pass


# alias для тестов, которые используют имя 'db'
@pytest.fixture()
async def db(session: AsyncSession):
    yield session


@pytest.fixture()
async def client(session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from app.api.v1.routers import analytics as analytics_router
    from app.api.v1.routers import choices as choices_router
    from app.api.v1.routers import materials as materials_router
    from app.api.v1.routers import questions as questions_router
    from app.api.v1.routers import tests as tests_router
    from app.services import answer_service

    cache_store: dict[str, object] = {}
    namespace_versions: dict[str, int] = {}

    async def fake_get(key: str):
        return cache_store.get(key)

    async def fake_set(key: str, value, ttl=None):
        cache_store[key] = value

    async def fake_get_namespace_version(namespace: str) -> int:
        return namespace_versions.get(namespace, 0)

    async def fake_bump_namespace(*namespaces: str) -> None:
        for namespace in namespaces:
            namespace_versions[namespace] = namespace_versions.get(namespace, 0) + 1

    async def fake_delete_pattern(pattern: str) -> None:
        # not required for versioned invalidation tests, keep as no-op for compatibility
        return None

    monkeypatch.setattr(materials_router, "get", fake_get, raising=False)
    monkeypatch.setattr(materials_router, "set", fake_set, raising=False)
    monkeypatch.setattr(materials_router, "get_cache_namespace_version", fake_get_namespace_version, raising=False)
    monkeypatch.setattr(materials_router, "bump_cache_namespace", fake_bump_namespace, raising=False)

    monkeypatch.setattr(tests_router, "get", fake_get, raising=False)
    monkeypatch.setattr(tests_router, "set", fake_set, raising=False)
    monkeypatch.setattr(tests_router, "get_cache_namespace_version", fake_get_namespace_version, raising=False)
    monkeypatch.setattr(tests_router, "bump_cache_namespace", fake_bump_namespace, raising=False)

    monkeypatch.setattr(questions_router, "get", fake_get, raising=False)
    monkeypatch.setattr(questions_router, "set", fake_set, raising=False)
    monkeypatch.setattr(questions_router, "get_cache_namespace_version", fake_get_namespace_version, raising=False)
    monkeypatch.setattr(questions_router, "bump_cache_namespace", fake_bump_namespace, raising=False)

    monkeypatch.setattr(choices_router, "bump_cache_namespace", fake_bump_namespace, raising=False)
    monkeypatch.setattr(analytics_router, "get", fake_get, raising=False)
    monkeypatch.setattr(analytics_router, "set", fake_set, raising=False)
    monkeypatch.setattr(analytics_router, "get_cache_namespace_version", fake_get_namespace_version, raising=False)
    monkeypatch.setattr(answer_service, "bump_cache_namespace", fake_bump_namespace, raising=False)
    monkeypatch.setattr(redis_cache, "delete_pattern", fake_delete_pattern, raising=False)

    previous_rate_limit_enabled = settings.rate_limit_enabled
    settings.rate_limit_enabled = False

    async def override_get_db():
        try:
            yield session
            await session.flush()
            await run_post_commit_tasks(session)
            await session.commit()
            session.expunge_all()
        except Exception:
            session.info.pop(POST_COMMIT_TASKS_KEY, None)
            await session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    settings.rate_limit_enabled = previous_rate_limit_enabled

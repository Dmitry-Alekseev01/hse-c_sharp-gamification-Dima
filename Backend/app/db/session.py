"""
app/db/session.py
DESCRIPTION: async SQLAlchemy engine & async_sessionmaker using settings.get_database_url()
- Uses SQLAlchemy 2.0 async engine (asyncpg).
- Export Base, engine, AsyncSessionLocal.
"""
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

Base = declarative_base()

DATABASE_URL = settings.get_database_url()

engine_kwargs = {
    "future": True,
    "echo": False,
}
if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout_seconds,
            "pool_recycle": settings.db_pool_recycle_seconds,
            "pool_pre_ping": settings.db_pool_pre_ping,
        }
    )

# create async engine
engine: AsyncEngine = create_async_engine(DATABASE_URL, **engine_kwargs)

# session factory
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

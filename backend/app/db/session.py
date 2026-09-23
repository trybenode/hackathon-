"""Purpose: Create the pooled async SQLAlchemy engine and request sessions.

Dependencies: SQLAlchemy async engine and app.core.config.
Used by: FastAPI dependencies, health checks, and domain services.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.async_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield one async database session per request."""

    async with async_session_factory() as session:
        yield session

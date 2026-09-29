"""Purpose: Provide an in-memory database session and seed records for tests.

Dependencies: SQLAlchemy async engine with aiosqlite, and app.models.
Used by: service and API tests that need real persistence.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.domain import User, Worker


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session against a fresh in-memory database.

    StaticPool keeps every checkout on the same connection, so the schema
    created here is visible to the code under test.
    """

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session

    await engine.dispose()


@pytest_asyncio.fixture
async def worker(session: AsyncSession) -> Worker:
    """Create a worker with its owning user."""

    user = User(email="worker@example.com", display_name="Ada Worker")
    session.add(user)
    await session.flush()

    record = Worker(user_id=user.id)
    session.add(record)
    await session.flush()
    return record

"""Purpose: Provide a database session and seed records for tests.

Dependencies: SQLAlchemy async engine (aiosqlite by default), and app.models.
Used by: service and API tests that need real persistence.

Tests run against in-memory SQLite by default because it is fast. Set
TEST_DATABASE_URL to run the same suite against Postgres, which is what the
deployed database is:

    createdb trust_test
    TEST_DATABASE_URL=postgresql+asyncpg://$(whoami)@localhost:5432/trust_test pytest
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.domain import User, Worker


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session against a database with a freshly created schema.

    For SQLite, StaticPool keeps every checkout on the same connection so the
    in-memory schema stays visible. For Postgres the schema is dropped and
    recreated per test, which keeps tests isolated at the cost of some speed.
    """

    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_async_engine(url)
    else:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

    async with engine.begin() as connection:
        if url:
            await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session

    await engine.dispose()


@pytest_asyncio.fixture
async def worker(session: AsyncSession) -> Worker:
    """Create a worker with its owning user."""

    user = User(email="worker@example.com", display_name="Jane A.")
    session.add(user)
    await session.flush()

    record = Worker(
        user_id=user.id,
        role="Cleaner",
        location="Lekki, Lagos",
        avatar_url="https://example.com/jane.jpg",
    )
    session.add(record)
    await session.flush()
    return record

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

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.models.domain import User, Worker
from app.services import document_store as document_store_module
from app.services import email_sender as email_sender_module
from app.services import escrow_provider as escrow_provider_module
from app.services.document_store import NullDocumentStore
from app.services.email_sender import LoggingEmailSender
from app.services.escrow_provider import StubEscrowProvider


@pytest.fixture(autouse=True)
def never_send_real_email(monkeypatch: pytest.MonkeyPatch) -> LoggingEmailSender:
    """Keep the suite offline even when RESEND_API_KEY is set in .env."""

    stub = LoggingEmailSender()
    monkeypatch.setattr(email_sender_module, "default_email_sender", stub)
    return stub


@pytest.fixture(autouse=True)
def never_upload_to_a_real_bucket(monkeypatch: pytest.MonkeyPatch) -> NullDocumentStore:
    """Keep the suite offline even when S3_BUCKET is set in .env."""

    stub = NullDocumentStore()
    monkeypatch.setattr(document_store_module, "default_document_store", stub)
    return stub


@pytest.fixture(autouse=True)
def never_move_real_money(monkeypatch: pytest.MonkeyPatch) -> StubEscrowProvider:
    """Keep the suite offline even when PAYSCROW_API_KEY is set in .env."""

    stub = StubEscrowProvider()
    monkeypatch.setattr(escrow_provider_module, "default_escrow_provider", stub)
    return stub


@pytest.fixture
def stand_in_checks_are_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Label stand-in KYC passes "sandbox", as once a real provider is wired up."""

    monkeypatch.setattr(get_settings(), "stand_in_checks_verify", False)


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

    user = User(email="worker@example.com", display_name="Jane A.", phone="08087654321")
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


async def give_guarantor(session: AsyncSession, worker: Worker) -> None:
    """Stand an active guarantee behind the worker, as creating job links needs."""

    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models.domain import AgreementStatus, GuarantorAgreement

    existing = await session.scalar(
        select(GuarantorAgreement).where(
            GuarantorAgreement.worker_id == worker.id,
            GuarantorAgreement.status == AgreementStatus.ACTIVE,
        )
    )
    if existing is not None:
        return
    person = User(email=f"guarantor-{worker.id.hex[:8]}@example.com", display_name="Grace Guarantor")
    session.add(person)
    await session.flush()
    session.add(
        GuarantorAgreement(
            worker_id=worker.id,
            guarantor_user_id=person.id,
            scope="Cleaning jobs",
            conditions="Covers no-show.",
            relationship_type="employer",
            status=AgreementStatus.ACTIVE,
            verified_at=datetime.now(UTC),
            valid_until=datetime.now(UTC) + timedelta(days=365),
        )
    )
    await session.flush()

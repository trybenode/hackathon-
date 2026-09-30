"""Purpose: Seed a guarantor with the guarantees the dashboard designs show.

Dependencies: SQLAlchemy async engine and app.models.
Used by: local development, so the dashboard runs on real rows.

Usage:
    cd backend
    .venv/bin/python scripts/seed_guarantor.py trybenode@gmail.com

Targets whatever DATABASE_URL resolves to; run `alembic upgrade head` first.

Creates two workers with jobs, one active guarantee and one whose job has
finished, plus a pending request so the "Action required" banner has something
to show. Re-running replaces that guarantor's seeded instruments.
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.domain import (  # noqa: E402
    AgreementStatus,
    AuditEvent,
    GuarantorAgreement,
    IdentityVerification,
    Job,
    JobStatus,
    JobType,
    Organization,
    OrganizationType,
    User,
    Worker,
)

DB_URL = get_settings().async_database_url

NOW = datetime.now(tz=UTC)


async def get_or_create_user(session, email: str, display_name: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=display_name)
        session.add(user)
        await session.flush()
    return user


async def get_or_create_worker(
    session, *, email: str, name: str, role: str, location: str
) -> Worker:
    user = await get_or_create_user(session, email, name)
    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if worker is None:
        worker = Worker(user_id=user.id, role=role, location=location)
        session.add(worker)
        await session.flush()
    else:
        worker.role, worker.location = role, location
    return worker


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: seed_guarantor.py <guarantor-email>")
        raise SystemExit(1)

    guarantor_email = sys.argv[1].strip().casefold()

    engine = create_async_engine(DB_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        guarantor = await get_or_create_user(session, guarantor_email, "Daniel Peters")

        # Start clean so re-running does not pile up duplicates.
        existing = (
            await session.scalars(
                select(GuarantorAgreement.id).where(
                    GuarantorAgreement.guarantor_user_id == guarantor.id
                )
            )
        ).all()
        if existing:
            await session.execute(
                delete(AuditEvent).where(AuditEvent.entity_id.in_(existing))
            )
            await session.execute(
                delete(GuarantorAgreement).where(GuarantorAgreement.id.in_(existing))
            )
        await session.execute(
            delete(IdentityVerification).where(IdentityVerification.user_id == guarantor.id)
        )

        organization = await session.scalar(select(Organization).limit(1))
        if organization is None:
            organization = Organization(
                name="Sparkle Homes", organization_type=OrganizationType.EMPLOYER
            )
            session.add(organization)
            await session.flush()

        jane = await get_or_create_worker(
            session,
            email="jane@example.com",
            name="Jane A",
            role="Cleaner",
            location="Lekki, Lagos",
        )
        daniella = await get_or_create_worker(
            session,
            email="daniella@example.com",
            name="Daniella k.",
            role="Pumber",
            location="Yaba, Lagos",
        )
        tomiwa = await get_or_create_worker(
            session,
            email="tomiwa@example.com",
            name="Tomiwa B.",
            role="Electrician",
            location="Ikeja, Lagos",
        )

        cleaning = Job(
            worker_id=jane.id,
            organization_id=organization.id,
            job_type=JobType.INDEPENDENT,
            status=JobStatus.IN_PROGRESS,
            title="Home cleaning",
            agreed_amount=Decimal("25000.00"),
        )
        sink = Job(
            worker_id=daniella.id,
            organization_id=organization.id,
            job_type=JobType.INDEPENDENT,
            status=JobStatus.COMPLETED,
            title="Sink fix",
            agreed_amount=Decimal("15000.00"),
        )
        rewire = Job(
            worker_id=tomiwa.id,
            organization_id=organization.id,
            job_type=JobType.INDEPENDENT,
            status=JobStatus.ACCEPTED,
            title="Socket rewiring",
            agreed_amount=Decimal("40000.00"),
        )
        session.add_all([cleaning, sink, rewire])
        await session.flush()

        # Identity checks the two live guarantees were activated against.
        session.add_all(
            [
                IdentityVerification(
                    user_id=guarantor.id,
                    provider="stub",
                    provider_reference="STUB-SEED-IDENTITY",
                    status="verified",
                    check_type="identity",
                ),
                IdentityVerification(
                    user_id=guarantor.id,
                    provider="stub",
                    provider_reference="STUB-SEED-LIVENESS",
                    status="verified",
                    check_type="liveness",
                ),
            ]
        )

        active = GuarantorAgreement(
            worker_id=jane.id,
            guarantor_user_id=guarantor.id,
            job_id=cleaning.id,
            scope="Home cleaning jobs in Lekki",
            conditions="Covers no-show and property damage claims.",
            relationship_type="sibling",
            guarantor_phone="+2348012345678",
            guarantor_address="12 Trust Street, Lagos",
            status=AgreementStatus.ACTIVE,
            valid_until=NOW + timedelta(days=10),
            signed_at=NOW - timedelta(days=7),
            verified_at=NOW - timedelta(days=7),
        )
        finished = GuarantorAgreement(
            worker_id=daniella.id,
            guarantor_user_id=guarantor.id,
            job_id=sink.id,
            scope="Plumbing callouts",
            conditions="Covers no-show and repeat visits.",
            relationship_type="colleague",
            guarantor_phone="+2348012345678",
            guarantor_address="12 Trust Street, Lagos",
            status=AgreementStatus.ACTIVE,
            valid_until=NOW + timedelta(days=120),
            signed_at=NOW - timedelta(days=40),
            verified_at=NOW - timedelta(days=40),
        )
        pending = GuarantorAgreement(
            worker_id=tomiwa.id,
            guarantor_user_id=guarantor.id,
            job_id=rewire.id,
            scope="Electrical work up to NGN 40,000",
            conditions="Covers no-show and rework.",
            relationship_type="other",
            guarantor_phone="+2348012345678",
            guarantor_address="12 Trust Street, Lagos",
            status=AgreementStatus.PENDING_SIGNATURE,
            valid_until=NOW + timedelta(days=90),
        )
        session.add_all([active, finished, pending])
        await session.flush()

        # A trail the "Recent activity" list can read.
        for agreement, actions in (
            (active, ("guarantor.created", "guarantor.signed", "guarantor.identity_submitted", "guarantor.identity_verified")),
            (finished, ("guarantor.created", "guarantor.signed", "guarantor.identity_verified")),
            (pending, ("guarantor.created",)),
        ):
            for offset, action in enumerate(actions):
                session.add(
                    AuditEvent(
                        actor_id=guarantor.id,
                        entity_type="guarantor_agreement",
                        entity_id=agreement.id,
                        action=action,
                        event_metadata={},
                    )
                )

        await session.commit()

        print(f"DATABASE_URL={DB_URL}")
        print(f"GUARANTOR={guarantor_email}")
        print(f"  active guarantee   : {active.id} (Jane A, Home cleaning)")
        print(f"  completed guarantee: {finished.id} (Daniella k., Sink fix)")
        print(f"  pending request    : {pending.id} (Tomiwa B., Socket rewiring)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

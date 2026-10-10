"""Purpose: Seed a worker whose portable record matches the designs.

Dependencies: SQLAlchemy async engine and app.models.
Used by: local development, so the portable record screens run on real rows.

Usage:
    cd backend
    .venv/bin/python scripts/seed_worker_record.py you@example.com

Targets whatever DATABASE_URL resolves to; run `alembic upgrade head` first.

Makes the email's owner a worker ("Jane Adams", cleaner) with a year of
verified jobs, a passed identity check, an active guarantor, and a handful of
outcomes imported from another platform. Sign in with that email and open
/worker/profile. Re-running replaces what this script seeded for that worker.
"""

import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.domain import (  # noqa: E402
    AgreementStatus,
    GuarantorAgreement,
    IdentityVerification,
    Job,
    JobStatus,
    JobType,
    NormalizedOutcome,
    Organization,
    OrganizationType,
    OutcomeSource,
    OutcomeStatus,
    RawOutcome,
    TrustAssessment,
    TrustAssessmentSignal,
    User,
    Worker,
)

DB_URL = get_settings().async_database_url
NOW = datetime.now(tz=UTC)

SEED_ORGANIZATION = "Portable Record Seed Clients"
NATIVE_SOURCE = "portable-record-seed"
IMPORT_SOURCE = "portable-record-seed-import"

#: Clients by pool number, so repeat hires come back under the same name.
CLIENT_NAMES = [
    "Peter James", "Amaka Obi", "John Parker", "Tunde Bello", "Ngozi Eze", "Sarah Ade",
    "Chidi Okafor", "Bisi Adeyemi", "Kemi Lawal", "Emeka Nwosu", "Funke Alabi", "Yemi Ojo",
]
AREAS = ["Lekki, Lagos", "Ikoyi, Lagos", "Victoria Island, Lagos", "Yaba, Lagos", "Ikeja, Lagos"]

#: (title, amount) for the kinds of job the history is made of.
JOB_KINDS = [
    ("Home cleaning", Decimal("15000.00")),
    ("Home cleaning", Decimal("15000.00")),
    ("Deep cleaning", Decimal("40000.00")),
    ("Office cleaning", Decimal("50000.00")),
]


def one_year_after(moment: datetime) -> datetime:
    try:
        return moment.replace(year=moment.year + 1)
    except ValueError:
        return moment.replace(year=moment.year + 1, day=28)


async def get_or_create_user(session, email: str, display_name: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=display_name)
        session.add(user)
        await session.flush()
    return user


async def get_or_create_source(session, name: str) -> OutcomeSource:
    source = await session.scalar(select(OutcomeSource).where(OutcomeSource.name == name))
    if source is None:
        source = OutcomeSource(name=name, normalization_version="1")
        session.add(source)
        await session.flush()
    return source


async def add_outcome(
    session,
    *,
    worker: Worker,
    source: OutcomeSource,
    occurred_at: datetime,
    status: OutcomeStatus,
    amount: Decimal,
    client_id: str | None,
    job: Job | None = None,
    confirmed: bool = True,
    cancelled_by: str | None = None,
    dispute_resolution: str | None = None,
    imported: bool = False,
    created_at: datetime | None = None,
    rating: int | None = None,
) -> None:
    key = f"seed-{uuid4().hex[:12]}"
    raw = RawOutcome(
        source_id=source.id,
        external_outcome_id=key,
        payload={"status": status.value},
        payload_checksum=uuid4().hex * 2,
    )
    session.add(raw)
    await session.flush()
    outcome = NormalizedOutcome(
        worker_id=worker.id,
        job_id=job.id if job else None,
        raw_outcome_id=raw.id,
        outcome_key=key,
        status=status,
        occurred_at=occurred_at,
        amount=amount,
        rating=Decimal(rating) if rating else None,
        completion_confirmed=confirmed,
        normalization_version="1",
        cancelled_by=cancelled_by,
        dispute_resolution=dispute_resolution,
        client_id=client_id,
        source_platform="CleanPro" if imported else "native",
        import_method="api" if imported else "native",
        verified=True,
        quality_flags=[],
    )
    if created_at is not None:
        outcome.created_at = created_at
    session.add(outcome)


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: seed_worker_record.py <worker-email>")
        raise SystemExit(1)

    email = sys.argv[1].strip().casefold()
    rng = random.Random(7)

    engine = create_async_engine(DB_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await get_or_create_user(session, email, "Jane Adams")
        # Payscrow needs the worker's (merchant's) phone to open escrow.
        user.phone = user.phone or "08087654321"
        worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
        if worker is None:
            worker = Worker(user_id=user.id)
            session.add(worker)
            await session.flush()
        worker.role, worker.location = "Cleaner", "Lekki, Lagos"

        native = await get_or_create_source(session, NATIVE_SOURCE)
        imported_source = await get_or_create_source(session, IMPORT_SOURCE)
        organization = await session.scalar(
            select(Organization).where(Organization.name == SEED_ORGANIZATION)
        )
        if organization is None:
            organization = Organization(
                name=SEED_ORGANIZATION, organization_type=OrganizationType.EMPLOYER
            )
            session.add(organization)
            await session.flush()

        # Start clean so re-running does not pile up duplicates.
        old_raw = (
            await session.scalars(
                select(NormalizedOutcome.raw_outcome_id).where(
                    NormalizedOutcome.worker_id == worker.id
                )
            )
        ).all()
        await session.execute(delete(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id))
        if old_raw:
            await session.execute(delete(RawOutcome).where(RawOutcome.id.in_(old_raw)))
        old_assessments = (
            await session.scalars(
                select(TrustAssessment.id).where(TrustAssessment.worker_id == worker.id)
            )
        ).all()
        if old_assessments:
            await session.execute(
                delete(TrustAssessmentSignal).where(
                    TrustAssessmentSignal.assessment_id.in_(old_assessments)
                )
            )
            await session.execute(delete(TrustAssessment).where(TrustAssessment.id.in_(old_assessments)))
        await session.execute(
            delete(GuarantorAgreement).where(GuarantorAgreement.worker_id == worker.id)
        )
        await session.execute(
            delete(Job).where(Job.worker_id == worker.id, Job.organization_id == organization.id)
        )
        await session.execute(
            delete(IdentityVerification).where(IdentityVerification.user_id == user.id)
        )

        # Identity: NIN and BVN checked together, plus liveness.
        verified_on = NOW - timedelta(days=26)
        for check in ("identity", "liveness"):
            session.add(
                IdentityVerification(
                    user_id=user.id,
                    provider="stub",
                    provider_reference=f"STUB-SEED-{check.upper()}",
                    status="verified",
                    check_type=check,
                    created_at=verified_on,
                )
            )

        # An active guarantor, a year from activation.
        guarantor = await get_or_create_user(session, "john.parker@example.com", "John Parker")
        session.add(
            GuarantorAgreement(
                worker_id=worker.id,
                guarantor_user_id=guarantor.id,
                scope="Home and office cleaning",
                conditions="Covers no-show and property damage claims.",
                relationship_type="employer",
                guarantor_phone="+2348000000000",
                guarantor_address="4 Admiralty Way, Lekki",
                status=AgreementStatus.ACTIVE,
                signed_at=verified_on,
                verified_at=verified_on,
                valid_until=one_year_after(verified_on),
            )
        )

        # A year of native jobs, every ten days or so, from a pool of clients
        # small enough that some of them hire again.
        for index in range(36):
            title, amount = JOB_KINDS[index % len(JOB_KINDS)]
            occurred = NOW - timedelta(days=4 + index * 10, hours=rng.randint(0, 8))
            pool = rng.randint(1, 24)
            client = f"client-{pool}"
            job = Job(
                worker_id=worker.id,
                organization_id=organization.id,
                job_type=JobType.INDEPENDENT,
                status=JobStatus.RELEASED,
                title=title,
                agreed_amount=amount,
                client_name=CLIENT_NAMES[pool % len(CLIENT_NAMES)],
                location=AREAS[index % len(AREAS)],
            )
            session.add(job)
            await session.flush()

            if index == 11:
                # The client called it off: not held against the worker.
                await add_outcome(
                    session, worker=worker, source=native, occurred_at=occurred,
                    status=OutcomeStatus.CANCELLED, amount=amount, client_id=client,
                    job=job, cancelled_by="client",
                )
                continue

            await add_outcome(
                session, worker=worker, source=native, occurred_at=occurred,
                status=OutcomeStatus.COMPLETED, amount=amount, client_id=client, job=job,
                # Most clients confirm; the rest released on the timer.
                confirmed=index % 6 != 3,
                # One dispute went against the worker.
                dispute_resolution="upheld" if index == 20 else None,
                # Confirming customers rate the job; most are happy.
                rating=(rng.choice((5, 5, 5, 4, 4, 3)) if index % 6 != 3 else None),
            )

        # Work verified elsewhere and imported two days ago.
        imported_on = NOW - timedelta(days=2)
        for index in range(8):
            await add_outcome(
                session, worker=worker, source=imported_source,
                occurred_at=NOW - timedelta(days=380 + index * 14),
                status=OutcomeStatus.COMPLETED, amount=Decimal("15000.00"),
                client_id=f"cleanpro-client-{index}", imported=True,
                created_at=imported_on,
            )

        await session.commit()

        print(f"DATABASE_URL={DB_URL}")
        print(f"WORKER={email} (Jane Adams, Cleaner) worker_id={worker.id}")
        print("  36 native jobs, 8 imported outcomes, identity verified, active guarantor")
        print("Sign in with that email, then open /worker/profile")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

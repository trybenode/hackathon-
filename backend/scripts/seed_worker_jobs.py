"""Purpose: Seed a worker's jobs in every escrow state the screens show.

Dependencies: SQLAlchemy async engine and app.models.
Used by: local development, so the Jobs, Job Details and Escrow screens run on
real rows without calling Payscrow.

Usage:
    cd backend
    .venv/bin/python scripts/seed_worker_jobs.py you@example.com

The email must already be a worker (run seed_worker_record.py first). Creates
six jobs, one per stage: waiting for the customer (link only), awaiting
payment, held, awaiting confirmation, disputed (by the customer), released.
Each has a job link: /j/<token> opens it as its customer.
Re-running replaces the jobs this script made for that worker.
"""

import asyncio
import secrets
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
    Dispute,
    DisputeStatus,
    EscrowStatus,
    EscrowTransaction,
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
SEED_ORGANIZATION = "Escrow Seed Clients"

JOBS = [
    # (title, amount, client, location, details, stage)
    ("Home cleaning", "25000.00", "Peter James", "Lekki, Lagos",
     [("bedrooms", "2"), ("Bathroom", "1"), ("Duration", "4 hours"), ("Timing", "flexible")], "held"),
    ("Office cleaning", "50000.00", "John Parker", "Victoria Island, Lagos",
     [("Rooms", "6"), ("Restrooms", "2"), ("Duration", "6 hours"), ("Timing", "evening")], "awaiting_confirmation"),
    ("Deep cleaning", "40000.00", "Amaka Obi", "Ikeja, Lagos",
     [("bedrooms", "3"), ("Bathroom", "2"), ("Duration", "8 hours"), ("Timing", "morning")], "released"),
    ("Move-out cleaning", "35000.00", "Tunde Bello", "Yaba, Lagos",
     [("bedrooms", "2"), ("Duration", "5 hours")], "disputed"),
    ("Post-party cleaning", "20000.00", "Ngozi Eze", "Surulere, Lagos",
     [("Rooms", "3"), ("Duration", "3 hours")], "awaiting_payment"),
    ("Window cleaning", "15000.00", None, "Lagos Island, Lagos", [], "awaiting_customer"),
]


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: seed_worker_jobs.py <worker-email>")
        raise SystemExit(1)

    email = sys.argv[1].strip().casefold()
    engine = create_async_engine(DB_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        worker = await session.scalar(select(Worker).where(Worker.user_id == user.id)) if user else None
        if worker is None:
            print(f"{email} is not a worker yet. Run seed_worker_record.py {email} first.")
            raise SystemExit(1)

        organization = await session.scalar(
            select(Organization).where(Organization.name == SEED_ORGANIZATION)
        )
        if organization is None:
            organization = Organization(name=SEED_ORGANIZATION, organization_type=OrganizationType.EMPLOYER)
            session.add(organization)
            await session.flush()

        # Start clean so re-running does not pile up duplicates.
        old = (
            await session.scalars(
                select(Job.id).where(Job.worker_id == worker.id, Job.organization_id == organization.id)
            )
        ).all()
        if old:
            await session.execute(delete(Dispute).where(Dispute.job_id.in_(old)))
            await session.execute(delete(EscrowTransaction).where(EscrowTransaction.job_id.in_(old)))
            await session.execute(delete(Job).where(Job.id.in_(old)))

        links: list[tuple[str, str]] = []
        for index, (title, amount, client, location, details, stage) in enumerate(JOBS):
            assigned = NOW - timedelta(days=9 - index, hours=3)
            funded = assigned + timedelta(minutes=20)
            completed = funded + timedelta(hours=5) if stage in {"awaiting_confirmation", "released"} else None
            job_status = {
                "awaiting_customer": JobStatus.DRAFT,
                "awaiting_payment": JobStatus.ACCEPTED,
                "held": JobStatus.IN_PROGRESS,
                "awaiting_confirmation": JobStatus.SUBMITTED,
                "disputed": JobStatus.DISPUTED,
                "released": JobStatus.RELEASED,
            }[stage]

            job = Job(
                worker_id=worker.id,
                organization_id=organization.id,
                job_type=JobType.INDEPENDENT,
                status=job_status,
                title=title,
                agreed_amount=Decimal(amount),
                client_name=client,
                client_email=f"{client.split()[0].lower()}@example.com" if client else None,
                client_phone="08012345678" if client else None,
                location=location,
                details=[{"label": label, "value": value} for label, value in details],
                scheduled_at=assigned + timedelta(days=1, hours=2),
                link_token=secrets.token_urlsafe(16),
                completed_at=completed,
                created_at=assigned,
            )
            session.add(job)
            await session.flush()
            links.append((stage, job.link_token))
            if stage == "awaiting_customer":
                continue

            number = f"MKT-SEED{index:04d}"
            session.add(
                EscrowTransaction(
                    job_id=job.id,
                    provider="seed",
                    provider_reference=number,
                    provider_transaction_id=None if stage == "awaiting_payment" else str(uuid4()),
                    payment_link=f"https://payscrow.dev/marketplace/pay?transId=SEED{index}",
                    total_payable=Decimal(amount) + Decimal("500.00"),
                    amount=Decimal(amount),
                    status={
                        "awaiting_payment": EscrowStatus.PENDING,
                        "released": EscrowStatus.RELEASED,
                    }.get(stage, EscrowStatus.HELD),
                    cover_active=stage == "held",
                    funded_at=None if stage == "awaiting_payment" else funded,
                    released_at=completed + timedelta(hours=2) if stage == "released" else None,
                    in_dispute=stage == "disputed",
                    dispute_stage="EvidenceCollection" if stage == "disputed" else None,
                )
            )
            if stage == "disputed":
                session.add(
                    Dispute(
                        job_id=job.id,
                        opened_by_id=None,
                        raised_by="customer",
                        reason="Agreement unfulfilled",
                        status=DisputeStatus.UNDER_REVIEW,
                    )
                )

        await session.commit()
        print(f"Seeded {len(JOBS)} jobs for {email}. Sign in, then open /worker")
        print("Customer job pages (no sign-in):")
        for stage, token in links:
            print(f"  {stage:22} /j/{token}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

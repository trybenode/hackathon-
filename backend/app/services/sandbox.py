"""Purpose: Give sandbox platform keys a fixed set of demo workers to call.

Dependencies: SQLAlchemy async sessions, app.models.domain and portability.
Used by: developer credential generation (seeding) and worker linking (the
published demo consent tokens), so a developer can try the API in minutes
without a real worker's consent.

Demo workers are flagged `is_sandbox`: only sandbox keys can see them, and
production keys never do. Their histories are made up but fixed, one per
trust band, so the same call always gets the same answer.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AgreementStatus,
    GuarantorAgreement,
    IdentityVerification,
    NormalizedOutcome,
    OutcomeSource,
    OutcomeStatus,
    RawOutcome,
    User,
    Worker,
)
from app.models.portability import PlatformGrant, PlatformKey
from app.services.portability import digest

SANDBOX = "sandbox"
SOURCE = "sandbox-demo"
#: Sandbox approvals outlive any demo; a worker's real approvals last a week.
GRANT_LIFETIME = timedelta(days=3650)
PERMISSIONS = ["read_history", "import_history"]


@dataclass(frozen=True)
class DemoWorker:
    slug: str
    name: str
    role: str
    location: str
    #: The band the history is shaped to land in.
    band: str
    jobs: int
    #: Share of jobs that ended badly, and how.
    worker_cancels: float
    no_shows: float
    disputes_upheld: int
    rating_range: tuple[float, float]
    #: Share of jobs from returning clients.
    repeat_share: float
    #: The demo guarantee's state: "active", "pending", "expired", or None.
    guarantee: str | None = None

    @property
    def consent_token(self) -> str:
        """Published in the sandbox docs; works only with sandbox keys."""

        return f"sandbox-consent-{self.slug}-demo-worker-token"

    @property
    def email(self) -> str:
        return f"{self.slug}@sandbox.credly.dev"


DEMO_WORKERS: tuple[DemoWorker, ...] = (
    DemoWorker("ada", "Ada Okafor", "Cleaner", "Lekki, Lagos", "High", 48, 0.0, 0.0, 0, (4.6, 5.0), 0.4, "active"),
    DemoWorker("tunde", "Tunde Bello", "Electrician", "Yaba, Lagos", "Medium", 30, 0.07, 0.03, 1, (3.8, 4.7), 0.2, "pending"),
    DemoWorker("bisi", "Bisi Adeyemi", "Plumber", "Ikeja, Lagos", "Low", 22, 0.18, 0.14, 3, (2.5, 4.0), 0.05, "expired"),
    DemoWorker("chidi", "Chidi Eze", "Painter", "Surulere, Lagos", "Building History", 2, 0.0, 0.0, 0, (4.0, 5.0), 0.0),
)
BY_TOKEN = {worker.consent_token: worker for worker in DEMO_WORKERS}


def _now() -> datetime:
    return datetime.now(UTC)


def _history(demo: DemoWorker, today: datetime) -> list[dict]:
    """The demo worker's jobs, the same every time for the same worker."""

    rng = random.Random(demo.slug)
    clients: list[str] = []
    rows = []
    for index in range(demo.jobs):
        if clients and rng.random() < demo.repeat_share:
            client = rng.choice(clients)
        else:
            client = f"{demo.slug}-client-{index}"
            clients.append(client)
        roll = rng.random()
        if roll < demo.no_shows:
            status, cancelled_by = OutcomeStatus.NO_SHOW, None
        elif roll < demo.no_shows + demo.worker_cancels:
            status, cancelled_by = OutcomeStatus.CANCELLED, "worker"
        else:
            status, cancelled_by = OutcomeStatus.COMPLETED, None
        low, high = demo.rating_range
        rows.append(
            {
                "key": f"{demo.slug}-{index:03d}",
                "status": status,
                "cancelled_by": cancelled_by,
                "rating": round(rng.uniform(low, high), 1) if status is OutcomeStatus.COMPLETED else None,
                "dispute": None,
                "client": client,
                "amount": Decimal(rng.choice([15000, 20000, 25000, 40000, 60000])),
                # Spread over the past year, oldest first.
                "at": today - timedelta(days=int(360 * (demo.jobs - index) / max(demo.jobs, 1))),
            }
        )
    completed = [row for row in rows if row["status"] is OutcomeStatus.COMPLETED]
    for row in completed[-demo.disputes_upheld:] if demo.disputes_upheld else []:
        row["dispute"] = "upheld"
    return rows


async def _source(session: AsyncSession) -> OutcomeSource:
    source = await session.scalar(select(OutcomeSource).where(OutcomeSource.name == SOURCE))
    if source is None:
        source = OutcomeSource(name=SOURCE, normalization_version="sandbox-v1")
        session.add(source)
        await session.flush()
    return source


async def _seed(session: AsyncSession, demo: DemoWorker, source: OutcomeSource, today: datetime) -> Worker:
    user = User(email=demo.email, display_name=demo.name)
    session.add(user)
    await session.flush()
    worker = Worker(user_id=user.id, role=demo.role, location=demo.location, is_sandbox=True)
    session.add(worker)
    await session.flush()

    for row in _history(demo, today):
        payload = {
            "status": row["status"].value,
            "rating": row["rating"],
            "cancelled_by": row["cancelled_by"],
            "dispute_resolution": row["dispute"],
            "client_id": row["client"],
        }
        raw = RawOutcome(
            source_id=source.id, external_outcome_id=row["key"], payload=payload,
            payload_checksum=digest(repr(sorted(payload.items()))),
        )
        session.add(raw)
        await session.flush()
        signals = ["completion_rate", "no_show_rate", "cancellation_rate", "dispute_rate", "repeat_hire_rate"]
        if row["rating"] is not None:
            signals.append("average_rating")
        session.add(
            NormalizedOutcome(
                worker_id=worker.id, raw_outcome_id=raw.id, outcome_key=row["key"], status=row["status"],
                occurred_at=row["at"], rating=Decimal(str(row["rating"])) if row["rating"] is not None else None,
                amount=row["amount"], completion_confirmed=row["status"] is OutcomeStatus.COMPLETED,
                quality_flags=[], normalization_version="sandbox-v1", cancelled_by=row["cancelled_by"],
                dispute_resolution=row["dispute"], client_id=digest(row["client"])[:16],
                source_platform=SOURCE, import_method="native", verified=True, available_signals=signals,
            )
        )
    await session.flush()
    return worker


async def _checks_and_guarantee(session: AsyncSession, demo: DemoWorker, worker: Worker, today: datetime) -> None:
    """Identity, liveness and the demo guarantee; added to older seeds too."""

    have = set(
        (await session.scalars(select(IdentityVerification.check_type).where(IdentityVerification.user_id == worker.user_id))).all()
    )
    for check in ("identity", "liveness"):
        if check not in have:
            session.add(
                IdentityVerification(
                    user_id=worker.user_id, provider=SANDBOX, status="verified", check_type=check,
                    provider_reference=f"SANDBOX-{check.upper()}-{demo.slug.upper()}",
                )
            )
    if demo.guarantee is None or await session.scalar(
        select(GuarantorAgreement.id).where(GuarantorAgreement.worker_id == worker.id)
    ):
        await session.flush()
        return

    guarantor = await session.scalar(select(User).where(User.email == f"guarantor-{demo.slug}@sandbox.credly.dev"))
    if guarantor is None:
        guarantor = User(email=f"guarantor-{demo.slug}@sandbox.credly.dev", display_name=f"{demo.name.split()[0]}'s Guarantor")
        session.add(guarantor)
        await session.flush()
    status, started, ends = {
        "active": (AgreementStatus.ACTIVE, today - timedelta(days=60), today + timedelta(days=305)),
        "pending": (AgreementStatus.PENDING_VERIFICATION, None, today + timedelta(days=5)),
        "expired": (AgreementStatus.EXPIRED, today - timedelta(days=400), today - timedelta(days=35)),
    }[demo.guarantee]
    session.add(
        GuarantorAgreement(
            worker_id=worker.id, guarantor_user_id=guarantor.id, scope=f"{demo.role} jobs",
            conditions="Covers no-show and property damage claims.", relationship_type="colleague",
            status=status, verified_at=started, signed_at=started or today - timedelta(days=2),
            valid_until=ends, closed_at=ends if status is AgreementStatus.EXPIRED else None,
        )
    )
    await session.flush()


async def ensure_demo_workers(session: AsyncSession, *, now: datetime | None = None) -> dict[str, Worker]:
    """The demo workers by slug, seeding any that do not exist yet."""

    today = now or _now()
    workers: dict[str, Worker] = {}
    source: OutcomeSource | None = None
    for demo in DEMO_WORKERS:
        worker = await session.scalar(
            select(Worker).join(User, User.id == Worker.user_id).where(User.email == demo.email)
        )
        if worker is None:
            source = source or await _source(session)
            worker = await _seed(session, demo, source, today)
        await _checks_and_guarantee(session, demo, worker, today)
        workers[demo.slug] = worker
    return workers


async def demo_grant(
    session: AsyncSession, principal: PlatformKey, token: str, *, now: datetime | None = None
) -> PlatformGrant | None:
    """The approval behind a published demo consent token, for this platform.

    Each platform gets its own approval row, so revoking or linking one
    platform's demo access never touches another's.
    """

    demo = BY_TOKEN.get(token)
    if demo is None or principal.environment != SANDBOX:
        return None
    workers = await ensure_demo_workers(session, now=now)
    token_hash = digest(f"{principal.organization_id}:{token}")
    grant = await session.scalar(select(PlatformGrant).where(PlatformGrant.token_hash == token_hash))
    if grant is None:
        grant = PlatformGrant(
            worker_id=workers[demo.slug].id,
            organization_id=principal.organization_id,
            token_hash=token_hash,
            permissions=PERMISSIONS,
            expires_at=(now or _now()) + GRANT_LIFETIME,
        )
        session.add(grant)
        await session.flush()
    return grant

"""Purpose: Walk one freelance job through Payscrow escrow, narrating each step.

Dependencies: SQLAlchemy async engine, app.services.escrow and the escrow provider.
Used by: demos to Payscrow and the team; it is the same code the API runs.

Usage:
    cd backend
    # Offline: nothing leaves the machine; a stand-in plays Payscrow.
    .venv/bin/python scripts/simulate_escrow.py you@example.com --mode offline

    # Sandbox: real calls to api.payscrow.dev. Pay with the printed link; the
    # paid webhook must reach this API, so PAYSCROW_WEBHOOK_URL has to be a
    # public address (e.g. a cloudflared tunnel) and the API must be running.
    .venv/bin/python scripts/simulate_escrow.py you@example.com --mode sandbox \\
        --customer-email inbox-you-can-read@example.com

The email must be a worker with a phone (run seed_worker_record.py first).
Payscrow emails the escrow code to the customer when they pay; in sandbox mode,
pass it with --code or type it when asked.
"""

import argparse
import asyncio
import json
import sys
import textwrap
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.domain import EscrowStatus, User, Worker  # noqa: E402
from app.services import escrow as escrow_service  # noqa: E402
from app.services import escrow_provider as provider_module  # noqa: E402
from app.services import insurance, job_notifications  # noqa: E402
from app.services.escrow_provider import (  # noqa: E402
    StubEscrowProvider,
    sign_webhook,
    stub_escrow_code,
    verify_webhook,
)

SETTINGS = get_settings()
STEP = 0


def say(title: str, body: str = "") -> None:
    global STEP
    STEP += 1
    print(f"\n[{STEP}] {title}")
    if body:
        print(textwrap.indent(textwrap.dedent(body).strip(), "    "))


def note(text: str) -> None:
    print(textwrap.indent(text, "    "))


async def wait_for_payment(factory, job_id, minutes: int) -> bool:
    deadline = time.monotonic() + minutes * 60
    while time.monotonic() < deadline:
        async with factory() as session:
            escrow = await escrow_service.latest_escrow(session, job_id)
            if escrow and escrow.status is EscrowStatus.HELD:
                return True
        print("    ...waiting for Payscrow's paid webhook", flush=True)
        await asyncio.sleep(10)
    return False


async def run(args: argparse.Namespace) -> None:
    offline = args.mode == "offline"
    if offline:
        provider_module.default_escrow_provider = StubEscrowProvider()

    engine = create_async_engine(SETTINGS.async_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    window = SETTINGS.escrow_confirmation_window_hours

    async with factory() as session:
        user = await session.scalar(select(User).where(User.email == args.worker_email.casefold()))
        worker = await session.scalar(select(Worker).where(Worker.user_id == user.id)) if user else None
        if worker is None:
            sys.exit(f"{args.worker_email} is not a worker. Run seed_worker_record.py first.")

        say(
            "Setup",
            f"""
            Mode:     {args.mode} ({'stand-in provider, nothing leaves this machine' if offline else 'Payscrow sandbox ' + SETTINGS.payscrow_base_url})
            Worker:   {user.display_name} <{user.email}> (Payscrow merchant)
            Customer: {args.customer_name} <{args.customer_email}> (Payscrow customer, no account)
            Rule:     money moves only on the customer's code or Payscrow's ruling
            """,
        )

        # 1. The worker creates the job link.
        job = await escrow_service.create_job_link(
            session, user, title=args.title, address="Lagos Island, Lagos",
            scheduled_at=datetime.now(tz=UTC) + timedelta(days=2), price=Decimal(args.amount),
        )
        await session.commit()
        say(
            "Worker creates a job link (POST /api/v1/me/jobs)",
            f"""
            {args.title}, NGN {args.amount}
            Link to share: {job_notifications.job_page_url(job)}
            """,
        )

        # 2-3. The customer opens it and pays into escrow.
        escrow = await escrow_service.start_payment(
            session, job.link_token, name=args.customer_name, email=args.customer_email,
            phone=args.customer_phone, return_url=job_notifications.job_page_url(job),
        )
        await session.commit()
        say(
            "Customer opens the link, enters their details, proceeds to payment",
            f"""
            POST /api/v1/public/jobs/{{token}}/payment -> Payscrow transactions/start
            Transaction: {escrow.provider_reference}
            Customer pays: NGN {escrow.total_payable} (job + NGN {escrow.micro_premium} job
                           protection + their share of Payscrow's charge)
            Payment link: {escrow.payment_link}
            """,
        )

    # 4. Payscrow confirms by signed webhook.
    if offline:
        payload = {
            "transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "transactionNumber": escrow.provider_reference,
            "externalReference": f"JOB-{job.id}",
            "paymentStatus": "Paid",
            "escrowStatus": "InEscrow",
            "amountPaid": str(escrow.total_payable),
            "currency": "NGN",
        }
        body = json.dumps(payload).encode()
        secret = SETTINGS.payscrow_webhook_secret or "demo-secret"
        headers = sign_webhook(secret, body)
        verified = verify_webhook(secret, body, headers["X-PayScrow-Signature"], headers["X-PayScrow-Timestamp"])
        async with factory() as session:
            outcome = await escrow_service.handle_webhook(
                session, payload, delivery_id=headers["X-PayScrow-Delivery-Id"]
            )
            await session.commit()
            policy = await insurance.policy_for(session, job.id)
        say(
            "Customer paid; Payscrow's signed webhook arrived",
            f"""
            Signature: {'valid' if verified else 'INVALID'}; amount matches: {'yes' if outcome == 'funded' else 'NO'}
            Money held in escrow; cover {policy.status.value if policy else 'n/a'}; worker emailed "Payment received".
            Payscrow emails the escrow code to the customer.
            """,
        )
    else:
        say("Waiting for the customer to pay", f"Open and pay: {escrow.payment_link}")
        if not SETTINGS.payscrow_webhook_url:
            note("PAYSCROW_WEBHOOK_URL is not set, so the webhook cannot reach us. Stopping.")
            await engine.dispose()
            return
        if not await wait_for_payment(factory, job.id, args.wait_minutes):
            note("No payment seen. The job stays awaiting payment.")
            await engine.dispose()
            return
        say("Payment confirmed by Payscrow's signed webhook", "Code emailed to the customer.")

    # 5. The worker marks it complete.
    async with factory() as session:
        person = await session.get(User, worker.user_id)
        await escrow_service.mark_complete(session, person, job.id)
        await session.commit()
    say(
        "Worker marks the job completed",
        f"""
        The customer is emailed a link to their job page and has {window} hours to
        enter the code and rate, or report a problem. Otherwise a dispute opens;
        the money is never released on a timer.
        """,
    )

    # 6-7. The customer releases with the code and a rating.
    if offline:
        code = stub_escrow_code()
        note(f"(The stand-in issued the customer the code {code}.)")
    else:
        code = args.code or input("    Escrow code from the customer's Payscrow email: ").strip()
    async with factory() as session:
        await escrow_service.release_by_customer(session, job.link_token, code=code, rating=args.rating)
        await session.commit()
    say(
        f"Customer enters the code and rates {args.rating} stars (POST /api/v1/public/jobs/{{token}}/release)",
        """
        We passed the code to Payscrow (applycode) and did not keep it.
        Payment released; worker emailed. The job and its rating are now a
        verified outcome on the worker's record, feeding the trust score.
        """,
    )

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("worker_email")
    parser.add_argument("--mode", choices=("offline", "sandbox"), default="offline")
    parser.add_argument("--title", default="Home cleaning")
    parser.add_argument("--amount", default="25000.00")
    parser.add_argument("--customer-name", default="Sarah Ade")
    parser.add_argument("--customer-email", default="customer.demo@example.com")
    parser.add_argument("--customer-phone", default="08012345678")
    parser.add_argument("--rating", type=int, default=5)
    parser.add_argument("--code", help="sandbox: the escrow code Payscrow emailed the customer")
    parser.add_argument("--wait-minutes", type=int, default=15)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()

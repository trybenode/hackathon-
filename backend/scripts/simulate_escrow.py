"""Purpose: Walk one job through Payscrow escrow, narrating each step, for demos.

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
        --client-email inbox-you-can-read@example.com --client-phone 08012345678

The email must be a worker (run seed_worker_record.py first). The worker is
Payscrow's merchant and the client its customer. Payscrow emails the escrow
code to the client when they pay; giving it to us is how the client confirms.
In sandbox mode, pass it with --code or type it when asked.
"""

import argparse
import asyncio
import json
import sys
import textwrap
import time
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
    days = SETTINGS.escrow_confirmation_reminder_days

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
            Client:   {args.client_name} <{args.client_email}> (Payscrow customer)
            Job:      {args.title}, NGN {args.amount}
            Rule:     only the client's escrow code releases money; an unconfirmed
                      client is reminded after {days} days, nothing is paid out
            """,
        )

        # 1. Open the job and its escrow.
        job, escrow = await escrow_service.open_job(
            session,
            escrow_service.JobRequest(
                worker_id=worker.id,
                title=args.title,
                amount=Decimal(args.amount),
                client_name=args.client_name,
                client_email=args.client_email,
                client_phone=args.client_phone,
                location="Lekki, Lagos",
                details=[{"label": "Duration", "value": "4 hours"}],
            ),
        )
        await session.commit()
        say(
            "Job opened; escrow started on Payscrow (POST /api/v3/marketplace/transactions/start)",
            f"""
            Transaction: {escrow.provider_reference}
            Client pays: NGN {escrow.total_payable} (job + client's share of the escrow charge)
            Payment link for the client: {escrow.payment_link}
            Worker screen: "Awaiting client payment"
            """,
        )

    # 2. The client pays; Payscrow tells us by signed webhook.
    if offline:
        payload = {
            "transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "transactionNumber": escrow.provider_reference,
            "externalReference": f"JOB-{job.id}",
            "paymentStatus": "Paid",
            "escrowStatus": "InEscrow",
            "amountPaid": str(escrow.total_payable),
            "currency": "NGN",
            "status": "InProgress",
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
        say(
            "Client paid; Payscrow's 'Transaction Paid' webhook arrived",
            f"""
            Signature (HMAC-SHA256 over "timestamp.body"): {'valid' if verified else 'INVALID'}
            Amount and currency match the order: {'yes' if outcome == 'funded' else 'NO'}
            Result: {outcome}; funds held. Worker screen: "In progress / Protected"
            Payscrow emails the escrow code to the client.
            """,
        )
    else:
        say(
            "Waiting for the client to pay",
            f"""
            Open the payment link and pay with Payscrow's sandbox test details:
              {escrow.payment_link}
            Payscrow will post 'Transaction Paid' to: {SETTINGS.payscrow_webhook_url or '(PAYSCROW_WEBHOOK_URL is not set!)'}
            """,
        )
        if not SETTINGS.payscrow_webhook_url:
            note("PAYSCROW_WEBHOOK_URL is not set, so the webhook cannot reach us. Stopping.")
            await engine.dispose()
            return
        if not await wait_for_payment(factory, job.id, args.wait_minutes):
            note("No payment seen. The job stays 'Awaiting client payment'.")
            await engine.dispose()
            return
        say(
            "Payment confirmed by Payscrow's signed webhook",
            "Funds held. Payscrow emails the escrow code to the client's inbox.",
        )

    # 3. The worker finishes.
    async with factory() as session:
        person = await session.get(User, worker.user_id)
        await escrow_service.mark_complete(session, person, job.id)
        await session.commit()
    say(
        "Worker taps 'Mark as complete'",
        f"""
        Job status: Submitted; awaiting the client's confirmation.
        If the client says nothing, they are reminded after {days} days.
        The money stays held: nothing is ever released on a timer.
        """,
    )

    # 4. The client confirms with their code; we apply it.
    if offline:
        code = stub_escrow_code()
        note(f"(The stand-in issued the client the code {code}.)")
    else:
        code = args.code or input("    Escrow code from the client's Payscrow email: ").strip()
    async with factory() as session:
        await escrow_service.release(session, job.id, by="client", code=code)
        await session.commit()
    say(
        "Client confirms the job by giving their escrow code",
        """
        POST /api/v1/jobs/{id}/client-confirmation {"code": "..."}
        We passed the code to Payscrow (POST /api/v3/escrow/escrowtransactions/applycode)
        and did not keep it. Funds released to the worker. Worker screen: "Released".
        """,
    )

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("worker_email")
    parser.add_argument("--mode", choices=("offline", "sandbox"), default="offline")
    parser.add_argument("--title", default="Home cleaning")
    parser.add_argument("--amount", default="25000.00")
    parser.add_argument("--client-name", default="Peter James")
    parser.add_argument("--client-email", default="client.demo@example.com")
    parser.add_argument("--client-phone", default="08012345678")
    parser.add_argument("--code", help="sandbox: the escrow code Payscrow emailed the client")
    parser.add_argument("--wait-minutes", type=int, default=15)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()

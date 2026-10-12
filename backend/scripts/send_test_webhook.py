"""Purpose: Send the local API a Payscrow-style signed webhook, for manual testing.

Dependencies: httpx and app.services.escrow_provider (the same signing code).
Used by: local testing of the escrow flow without a Payscrow payment.

Usage:
    cd backend
    # The client paid: funds become held.
    .venv/bin/python scripts/send_test_webhook.py paid MKT-05893531
    # Payscrow ruled on a dispute: Refund, Close or Split.
    .venv/bin/python scripts/send_test_webhook.py ruling MKT-05893531 --resolution Refund

Signs with PAYSCROW_WEBHOOK_SECRET, so the API accepts it exactly as it would
Payscrow's. The transaction number is in POST /jobs's response and on the
worker's escrow screen.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.escrow_provider import sign_webhook  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("event", choices=("paid", "ruling"))
    parser.add_argument("transaction_number")
    parser.add_argument("--amount", help="paid: amount paid; defaults to what the order expects")
    parser.add_argument("--resolution", choices=("Refund", "Close", "Split"), default="Close")
    parser.add_argument("--api", default="http://localhost:8000/api/v1")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.payscrow_webhook_secret:
        sys.exit("PAYSCROW_WEBHOOK_SECRET is not set, so the API would reject any webhook.")

    if args.event == "paid":
        payload = {
            "transactionId": str(uuid.uuid4()),
            "transactionNumber": args.transaction_number,
            "paymentStatus": "Paid",
            "escrowStatus": "InEscrow",
            "currency": "NGN",
            "status": "InProgress",
        }
        if args.amount:
            payload["amountPaid"] = args.amount
    else:
        payload = {
            "event": "dispute.status_changed",
            "eventId": str(uuid.uuid4()),
            "transactionNumber": args.transaction_number,
            "inDispute": False,
            "disputeStage": "Resolved",
            "disputeStatus": "Resolved",
            "resolutionType": args.resolution,
        }

    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", **sign_webhook(settings.payscrow_webhook_secret, body)}
    response = httpx.post(f"{args.api}/webhooks/payscrow", content=body, headers=headers, timeout=15)
    print(response.status_code, response.text)


if __name__ == "__main__":
    main()

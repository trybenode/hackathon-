"""Operator review of developer verification (KYC + KYB) and name changes.

    python scripts/review_developer.py list
    python scripts/review_developer.py approve alex@company.com
    python scripts/review_developer.py reject alex@company.com --note "CAC certificate is unreadable"
    python scripts/review_developer.py approve-name alex@company.com
    python scripts/review_developer.py reject-name alex@company.com

Approval makes the developer's platform organization, which unlocks API
credentials on their dashboard. Documents are in the bucket under
developer-documents/<account id>/.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select  # noqa: E402

from app.db.session import async_session_factory  # noqa: E402
from app.models.developer import DeveloperAccount, NameChangeRequest, ReviewStatus  # noqa: E402
from app.models.domain import User  # noqa: E402
from app.services import developers  # noqa: E402


async def account_by_email(session, email: str) -> DeveloperAccount:
    user = await session.scalar(select(User).where(User.email == email.strip().casefold()))
    account = await session.scalar(select(DeveloperAccount).where(DeveloperAccount.user_id == user.id)) if user else None
    if account is None:
        sys.exit(f"{email} has no developer profile.")
    return account


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["list", "approve", "reject", "approve-name", "reject-name"])
    parser.add_argument("email", nargs="?")
    parser.add_argument("--note", default="", help="Why a submission is rejected; the developer sees it")
    args = parser.parse_args()
    if args.action != "list" and not args.email:
        parser.error("an email is required")
    if args.action == "reject" and not args.note.strip():
        parser.error("--note is required when rejecting, so the developer knows what to fix")

    async with async_session_factory() as session:
        if args.action == "list":
            waiting = (await session.execute(
                select(User.email, DeveloperAccount)
                .join(DeveloperAccount, DeveloperAccount.user_id == User.id)
                .where(DeveloperAccount.kyb_status == ReviewStatus.UNDER_REVIEW)
                .order_by(DeveloperAccount.submitted_at)
            )).all()
            print(f"Verification under review: {len(waiting)}")
            for email, account in waiting:
                print(f"  {email}  {account.full_name} · {account.business_name} "
                      f"({developers.BUSINESS_TYPES.get(account.business_type, account.business_type)}, "
                      f"reg. no. {account.registration_number}, TIN {account.tax_id}) "
                      f"· documents developer-documents/{account.id}/ · submitted {account.submitted_at:%d %b %H:%M}")
            names = (await session.execute(
                select(User.email, NameChangeRequest)
                .join(DeveloperAccount, DeveloperAccount.id == NameChangeRequest.account_id)
                .join(User, User.id == DeveloperAccount.user_id)
                .where(NameChangeRequest.status == ReviewStatus.UNDER_REVIEW)
            )).all()
            print(f"Name changes under review: {len(names)}")
            for email, request in names:
                print(f"  {email}  {request.current_name} → {request.new_name} "
                      f"({developers.NAME_CHANGE_REASONS.get(request.reason, request.reason)})")
            return

        account = await account_by_email(session, args.email)
        if args.action == "approve":
            organization = await developers.approve(session, account)
            print(f"Approved. Platform organization: {organization.name} ({organization.id})")
        elif args.action == "reject":
            await developers.reject(session, account, args.note)
            print("Rejected; the developer can fix it and submit again.")
        else:
            request = await developers.open_name_change(session, account)
            if request is None:
                sys.exit("No name change under review for that developer.")
            await developers.review_name_change(session, request, approved=args.action == "approve-name")
            print("Name change " + ("approved." if args.action == "approve-name" else "rejected."))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())

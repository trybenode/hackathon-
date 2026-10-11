"""Operator review of developer verification (KYC + KYB), name changes and attest requests.

    python scripts/review_developer.py list
    python scripts/review_developer.py approve alex@company.com
    python scripts/review_developer.py reject alex@company.com --note "CAC certificate is unreadable"
    python scripts/review_developer.py approve-name alex@company.com
    python scripts/review_developer.py reject-name alex@company.com
    python scripts/review_developer.py approve-attest pk_live_3f9a1c2b4d5e6f70
    python scripts/review_developer.py reject-attest pk_live_3f9a1c2b4d5e6f70

Approval makes the developer's platform organization, which unlocks API
credentials on their dashboard. Verification and attest decisions are emailed
to the developer. Documents are in the bucket under developer-documents/<account id>/.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select  # noqa: E402

from app.db.session import async_session_factory  # noqa: E402
from app.models.developer import DeveloperAccount, NameChangeRequest, ReviewStatus  # noqa: E402
from app.models.domain import Organization, User  # noqa: E402
from app.models.portability import PlatformKey  # noqa: E402
from app.services import developer_notifications as notify  # noqa: E402
from app.services import developers  # noqa: E402


async def account_by_email(session, email: str) -> DeveloperAccount:
    user = await session.scalar(select(User).where(User.email == email.strip().casefold()))
    account = await session.scalar(select(DeveloperAccount).where(DeveloperAccount.user_id == user.id)) if user else None
    if account is None:
        sys.exit(f"{email} has no developer profile.")
    return account


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "action",
        choices=["list", "approve", "reject", "approve-name", "reject-name", "approve-attest", "reject-attest"],
    )
    parser.add_argument("email", nargs="?", help="The developer's email, or a key ID for attest decisions")
    parser.add_argument("--note", default="", help="Why a submission is rejected; the developer sees it")
    args = parser.parse_args()
    if args.action != "list" and not args.email:
        parser.error("an email (or, for attest decisions, a key ID) is required")
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
            attests = (await session.execute(
                select(PlatformKey, Organization.name)
                .join(Organization, Organization.id == PlatformKey.organization_id)
                .where(PlatformKey.attest_requested_at.is_not(None), PlatformKey.revoked_at.is_(None))
                .order_by(PlatformKey.attest_requested_at)
            )).all()
            print(f"Attest requests: {len(attests)}")
            for key, business in attests:
                print(f"  {key.key_id}  {business} · {key.name} · asked {key.attest_requested_at:%d %b %H:%M}")
            return

        if args.action in ("approve-attest", "reject-attest"):
            key = await session.scalar(select(PlatformKey).where(PlatformKey.key_id == args.email.strip()))
            if key is None:
                sys.exit("No key with that ID.")
            approved = args.action == "approve-attest"
            await developers.decide_attest(session, key, approved=approved)
            owner = await session.get(User, key.created_by_user_id) if key.created_by_user_id else None
            await session.commit()
            if owner:
                await notify.attest_decided(owner.email, key.name or "API key", approved)
            print("Attest " + ("approved: its imports now count as verified." if approved else "declined."))
            return

        account = await account_by_email(session, args.email)
        email = args.email.strip().casefold()
        if args.action == "approve":
            organization = await developers.approve(session, account)
            await session.commit()
            await notify.kyb_approved(email, organization.name)
            print(f"Approved and emailed. Platform organization: {organization.name} ({organization.id})")
        elif args.action == "reject":
            await developers.reject(session, account, args.note)
            await session.commit()
            await notify.kyb_rejected(email, args.note.strip())
            print("Rejected and emailed; the developer can fix it and submit again.")
        else:
            request = await developers.open_name_change(session, account)
            if request is None:
                sys.exit("No name change under review for that developer.")
            await developers.review_name_change(session, request, approved=args.action == "approve-name")
            await session.commit()
            print("Name change " + ("approved." if args.action == "approve-name" else "rejected."))


if __name__ == "__main__":
    asyncio.run(main())

"""Assign/revoke explicit reviewer roles using trusted operator DB access; never creates user accounts."""

import argparse
import asyncio
from uuid import UUID
from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.admission import ReviewMembership
from app.models.domain import Organization, User
from app.services.feature_common import audit, now


async def main() -> None:
    """Record every privileged assignment, scope, operator and human reason."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["grant", "revoke"])
    parser.add_argument("email")
    parser.add_argument(
        "--scope", required=True, help="operations or an existing organization UUID"
    )
    parser.add_argument(
        "--environment", choices=["production", "sandbox"], default="production"
    )
    parser.add_argument(
        "--operator",
        required=True,
        help="Existing operator account email for the audit record",
    )
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    if len(args.reason.strip()) < 10:
        parser.error("A reason of at least ten characters is required")
    async with async_session_factory() as session:
        user = await session.scalar(
            select(User).where(
                User.email == args.email.strip().casefold(), User.is_active.is_(True)
            )
        )
        actor = await session.scalar(
            select(User).where(
                User.email == args.operator.strip().casefold(), User.is_active.is_(True)
            )
        )
        if not user or not actor:
            parser.error("Both user and operator must be existing active accounts")
        if args.scope != "operations":
            try:
                org = await session.get(Organization, UUID(args.scope))
            except ValueError:
                org = None
            if not org:
                parser.error(
                    "Scope must be operations or an existing organization UUID"
                )
        elif args.environment != "production":
            parser.error("Operations role uses the production review scope")
        row = await session.scalar(
            select(ReviewMembership)
            .where(
                ReviewMembership.user_id == user.id,
                ReviewMembership.scope == args.scope,
                ReviewMembership.environment == args.environment,
            )
            .with_for_update()
        )
        if not row:
            if args.action == "revoke":
                parser.error("No matching role exists")
            row = ReviewMembership(
                user_id=user.id, scope=args.scope, environment=args.environment
            )
            session.add(row)
            await session.flush()
        row.revoked_at = now() if args.action == "revoke" else None
        audit(
            session,
            actor.id,
            "review_membership",
            row.id,
            args.action,
            {
                "reason": args.reason,
                "scope": args.scope,
                "environment": args.environment,
            },
        )
        await session.commit()
        print(
            "Reviewer role updated; no account session or worker evidence was changed."
        )


if __name__ == "__main__":
    asyncio.run(main())

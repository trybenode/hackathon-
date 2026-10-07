"""Operator-only platform key issuance/revocation; no public enrollment API."""
import argparse
import asyncio
import secrets
import sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import async_session_factory
from app.models.domain import Organization
from app.models.portability import PlatformKey
from app.services.portability import digest, now

async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["issue", "revoke"])
    parser.add_argument("id", type=UUID, help="Organization UUID for issue; key UUID for revoke")
    parser.add_argument("--can-attest", action="store_true", help="Only after reviewing authority to attest own outcomes")
    args = parser.parse_args()
    async with async_session_factory() as session:
        if args.action == "revoke":
            row = await session.get(PlatformKey, args.id)
            if row is None: parser.error("Unknown key")
            row.revoked_at = now()
            await session.commit()
            print("Key revoked.")
        else:
            org = await session.get(Organization, args.id)
            if org is None: parser.error("Unknown organization; provision/review it first")
            secret = secrets.token_urlsafe(32)
            row = PlatformKey(organization_id=org.id, key_hash=digest(secret), can_attest=args.can_attest)
            session.add(row)
            await session.commit()
            print(f"Key ID: {row.id}\nSecret (shown once): {secret}")

if __name__ == "__main__": asyncio.run(main())

"""Purpose: Issue and verify email login codes, and mint guarantor sessions.

Dependencies: SQLAlchemy async sessions, app.models.domain, app.services.email_sender.
Used by: the auth endpoints behind the guarantor sign-in screen.

Sign-in is deliberately light: a guarantor proves they own the email address an
instrument was addressed to, and gets a session cookie. There is no password.

Codes and session tokens are stored as hashes, so neither table can be used to
sign in as someone else. Comparisons are constant-time.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import LoginCode, User, UserSession
from app.services import email_sender as email_sender_module
from app.services.email_sender import EmailMessage, EmailSender
from app.services.email_templates import login_code_html, login_code_subject, login_code_text

#: Matches the six boxes on the sign-in screen.
CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=10)
#: How long a guarantor stays signed in.
SESSION_TTL = timedelta(days=30)
#: A new code cannot be requested until this has passed.
RESEND_COOLDOWN = timedelta(seconds=60)
#: Wrong guesses allowed before a code is burned.
MAX_ATTEMPTS = 5

SESSION_COOKIE = "guarantor_session"


class AuthError(Exception):
    """Base class for sign-in failures."""


class ResendTooSoonError(AuthError):
    """A code was requested again before the cooldown elapsed."""


class InvalidCodeError(AuthError):
    """The code was wrong, expired, already used, or out of attempts."""


class UnknownAccountError(AuthError):
    """No account exists for that address."""


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalise_email(email: str) -> str:
    return email.strip().casefold()


def generate_code() -> str:
    """A zero-padded numeric code, uniformly random."""

    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def request_login_code(
    session: AsyncSession,
    email: str,
    *,
    sender: EmailSender | None = None,
    now: datetime | None = None,
) -> str:
    """Email a fresh login code and return it for tests and local development.

    The caller must never expose the returned code outside a development
    environment. Callers should respond identically whether or not an account
    exists, so this does not reveal that either.
    """

    moment = now or _now()
    address = normalise_email(email)

    latest = await session.scalar(
        select(LoginCode)
        .where(LoginCode.email == address)
        .order_by(LoginCode.created_at.desc())
        .limit(1)
    )
    if latest is not None and latest.created_at is not None:
        since = moment - _as_aware(latest.created_at)
        if since < RESEND_COOLDOWN and latest.consumed_at is None:
            raise ResendTooSoonError(
                f"Wait {int((RESEND_COOLDOWN - since).total_seconds())}s before asking again."
            )

    code = generate_code()
    session.add(
        LoginCode(
            email=address,
            code_hash=_hash(code),
            expires_at=moment + CODE_TTL,
        )
    )

    minutes = int(CODE_TTL.total_seconds() // 60)
    # Resolved at call time so tests (and a later config change) can swap it.
    await (sender or email_sender_module.default_email_sender).send(
        EmailMessage(
            to=address,
            subject=login_code_subject(code),
            body=login_code_text(code, minutes=minutes),
            html=login_code_html(code, minutes=minutes),
        )
    )
    return code


async def verify_login_code(
    session: AsyncSession,
    email: str,
    code: str,
    *,
    create_account: bool = False,
    now: datetime | None = None,
) -> tuple[User, str]:
    """Check a code and open a session, returning the user and session token.

    With `create_account` (signing up, or claiming a guarantor invite) a new
    address gets an account; otherwise only existing accounts can sign in.
    The token is returned once, to be set as an HTTP-only cookie; only its
    hash is stored.
    """

    moment = now or _now()
    address = normalise_email(email)

    record = await session.scalar(
        select(LoginCode)
        .where(LoginCode.email == address, LoginCode.consumed_at.is_(None))
        .order_by(LoginCode.created_at.desc())
        .limit(1)
    )
    if record is None:
        raise InvalidCodeError("That code is not valid. Ask for a new one.")

    if _as_aware(record.expires_at) <= moment:
        raise InvalidCodeError("That code has expired. Ask for a new one.")

    if record.attempts >= MAX_ATTEMPTS:
        raise InvalidCodeError("Too many attempts. Ask for a new code.")

    record.attempts += 1
    if not hmac.compare_digest(record.code_hash, _hash(code.strip())):
        raise InvalidCodeError("That code is not correct.")

    user = await session.scalar(select(User).where(User.email == address))
    if user is None and create_account:
        # The name comes with the identity details, or from the invite.
        user = User(email=address, display_name="")
        session.add(user)
        await session.flush()
    if user is None:
        raise UnknownAccountError(
            "We have no account for that address. New workers can sign up from Get started."
        )

    record.consumed_at = moment
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=moment + SESSION_TTL,
        )
    )
    return user, token


async def resolve_session(
    session: AsyncSession, token: str, *, now: datetime | None = None
) -> User | None:
    """Return the signed-in user for a session token, or None."""

    moment = now or _now()
    record = await session.scalar(
        select(UserSession).where(
            UserSession.token_hash == _hash(token),
            UserSession.revoked_at.is_(None),
        )
    )
    if record is None or _as_aware(record.expires_at) <= moment:
        return None

    return await session.get(User, record.user_id)


async def end_session(
    session: AsyncSession, token: str, *, now: datetime | None = None
) -> None:
    """Revoke a session so the cookie stops working."""

    record = await session.scalar(
        select(UserSession).where(UserSession.token_hash == _hash(token))
    )
    if record is not None and record.revoked_at is None:
        record.revoked_at = now or _now()


async def user_instrument_ids(session: AsyncSession, user_id: UUID) -> list[UUID]:
    """Instrument ids this user stands behind, for scoping dashboard reads."""

    from app.models.domain import GuarantorAgreement

    rows = await session.scalars(
        select(GuarantorAgreement.id).where(GuarantorAgreement.guarantor_user_id == user_id)
    )
    return list(rows)

"""Purpose: Verify guarantor instrument lifecycle rules and signature capture.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.guarantor.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AgreementStatus,
    AuditEvent,
    ElectronicSignature,
    IdentityVerification,
    Worker,
)
from app.schemas.api import (
    GuarantorDetails,
    GuarantorInstrumentCreateRequest,
    GuarantorRelationship,
    GuarantorSignRequest,
    SignatureMetadata,
)
from app.services import guarantor as service
from app.services.identity_provider import IdentitySubmission, LivenessSubmission

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def build_request(worker: Worker, *, valid_until: datetime | None = None) -> GuarantorInstrumentCreateRequest:
    return GuarantorInstrumentCreateRequest(
        worker_id=worker.id,
        guarantor=GuarantorDetails(
            full_name="Grace Guarantor",
            phone="+2348012345678",
            email="grace@example.com",
            relationship=GuarantorRelationship.SIBLING,
            address="12 Trust Street, Lagos",
        ),
        scope="Domestic cleaning jobs up to NGN 50,000",
        conditions="Covers no-show and property damage claims.",
        valid_until=valid_until or NOW + timedelta(days=30),
    )


def build_signature(*, accepted: bool = True, at: datetime | None = None) -> GuarantorSignRequest:
    return GuarantorSignRequest(
        signer_name="Grace Guarantor",
        signer_phone="+2348012345678",
        accepted=accepted,
        signature_metadata=SignatureMetadata(
            ip="102.89.1.7",
            user_agent="Mozilla/5.0 (iPhone)",
            timestamp=at or NOW + timedelta(hours=1),
        ),
    )


def build_submission(**overrides) -> IdentitySubmission:
    fields = {
        "first_name": "Grace",
        "last_name": "Guarantor",
        "phone": "+2348012345678",
        "address": "12 Trust Street, Lagos",
        "nin": "12345678901",
        "bvn": "10987654321",
    }
    fields.update(overrides)
    return IdentitySubmission(**fields)


def build_frame(size: int = 512) -> LivenessSubmission:
    """A capture large enough for the stub provider to accept."""

    return LivenessSubmission(image=b"\xff\xd8" + b"x" * size)


async def activate(session: AsyncSession, instrument_id, *, at: datetime | None = None):
    """Accept the terms, pass the identity check, then pass liveness."""

    moment = at or NOW
    await service.sign_instrument(session, instrument_id, build_signature(at=moment), now=moment)
    await service.submit_identity_check(session, instrument_id, build_submission())
    return await service.complete_liveness_check(
        session, instrument_id, build_frame(), now=moment
    )


async def test_create_defaults_to_pending_signature(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)

    assert agreement.status is AgreementStatus.PENDING_SIGNATURE
    assert agreement.guarantor_phone == "+2348012345678"
    assert agreement.guarantor_address == "12 Trust Street, Lagos"


async def test_create_as_draft_then_send(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(
        session, build_request(worker), as_draft=True, now=NOW
    )
    assert agreement.status is AgreementStatus.DRAFT

    sent = await service.send_for_signature(session, agreement.id, now=NOW)
    assert sent.status is AgreementStatus.PENDING_SIGNATURE


async def test_create_rejects_self_guarantee(session: AsyncSession, worker: Worker) -> None:
    request = build_request(worker)
    request.guarantor.email = "worker@example.com"

    with pytest.raises(service.SelfGuaranteeError):
        await service.create_instrument(session, request, now=NOW)


async def test_create_rejects_past_validity(session: AsyncSession, worker: Worker) -> None:
    request = build_request(worker, valid_until=NOW - timedelta(days=1))

    with pytest.raises(service.ValidityWindowError):
        await service.create_instrument(session, request, now=NOW)


async def test_create_rejects_unknown_worker(session: AsyncSession, worker: Worker) -> None:
    request = build_request(worker)
    request.worker_id = worker.user_id  # A user id is never a worker id.

    with pytest.raises(service.WorkerNotFoundError):
        await service.create_instrument(session, request, now=NOW)


async def test_accept_waits_for_verification_and_stores_evidence(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    signed_at = NOW + timedelta(hours=1)

    result = await service.sign_instrument(
        session, agreement.id, build_signature(at=signed_at), now=signed_at
    )

    # Accepting the terms does not make the guarantee live on its own.
    assert result.status is AgreementStatus.PENDING_VERIFICATION
    assert result.signed_at == signed_at
    assert result.verified_at is None

    signature = await session.scalar(
        select(ElectronicSignature).where(ElectronicSignature.agreement_id == agreement.id)
    )
    assert signature is not None
    assert signature.accepted is True
    assert signature.signature_hash == service.build_signature_hash(
        agreement_id=agreement.id,
        signer_name="Grace Guarantor",
        signer_phone="+2348012345678",
        accepted=True,
        signed_at=signed_at,
        ip_address="102.89.1.7",
        user_agent="Mozilla/5.0 (iPhone)",
    )


async def test_signature_hash_changes_with_evidence(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    base = dict(
        agreement_id=agreement.id,
        signer_name="Grace Guarantor",
        signer_phone="+2348012345678",
        accepted=True,
        signed_at=NOW,
        ip_address="102.89.1.7",
        user_agent="Mozilla/5.0 (iPhone)",
    )

    assert service.build_signature_hash(**base) != service.build_signature_hash(
        **{**base, "accepted": False}
    )
    assert service.build_signature_hash(**base) != service.build_signature_hash(
        **{**base, "ip_address": "10.0.0.1"}
    )


async def test_identity_check_stores_only_the_reference(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)

    record = await service.submit_identity_check(session, agreement.id, build_submission())
    await session.flush()

    assert record.status == "verified"
    assert record.check_type == "identity"
    assert record.provider_reference.startswith("STUB-")

    # The identity numbers must appear nowhere in the stored row.
    stored = " ".join(
        str(value) for value in (record.provider, record.provider_reference, record.status)
    )
    assert "12345678901" not in stored
    assert "10987654321" not in stored

    # Submitting alone does not activate the guarantee.
    assert agreement.status is AgreementStatus.PENDING_VERIFICATION


async def test_identity_check_rejects_malformed_numbers(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)

    with pytest.raises(service.IdentityCheckFailedError):
        await service.submit_identity_check(
            session, agreement.id, build_submission(nin="123")
        )

    # The failed attempt is still recorded for audit.
    record = await session.scalar(
        select(IdentityVerification).where(
            IdentityVerification.user_id == agreement.guarantor_user_id
        )
    )
    assert record is not None
    assert record.status == "failed"


async def test_liveness_requires_a_passed_identity_check(
    session: AsyncSession, worker: Worker
) -> None:
    """A guarantee needs both checks: a selfie alone cannot activate it."""

    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)

    with pytest.raises(service.IdentityCheckMissingError):
        await service.complete_liveness_check(session, agreement.id, build_frame(), now=NOW)

    assert agreement.status is AgreementStatus.PENDING_VERIFICATION


async def test_liveness_activates_once_identity_has_passed(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)
    await service.submit_identity_check(session, agreement.id, build_submission())

    result = await service.complete_liveness_check(session, agreement.id, build_frame(), now=NOW)

    assert result.status is AgreementStatus.ACTIVE


async def test_liveness_rejects_an_empty_capture(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)
    await service.submit_identity_check(session, agreement.id, build_submission())

    with pytest.raises(service.LivenessCheckFailedError):
        await service.complete_liveness_check(
            session, agreement.id, LivenessSubmission(image=b""), now=NOW
        )

    assert agreement.status is AgreementStatus.PENDING_VERIFICATION
    failed = await session.scalar(
        select(IdentityVerification).where(IdentityVerification.check_type == "liveness")
    )
    assert failed is not None and failed.status == "failed"


async def test_verification_activates_the_guarantee(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)
    await service.submit_identity_check(session, agreement.id, build_submission())

    verified_at = NOW + timedelta(hours=2)
    result = await service.complete_liveness_check(
        session, agreement.id, build_frame(), now=verified_at
    )

    assert result.status is AgreementStatus.ACTIVE
    assert result.verified_at == verified_at

    liveness = await session.scalar(
        select(IdentityVerification).where(
            IdentityVerification.user_id == agreement.guarantor_user_id,
            IdentityVerification.check_type == "liveness",
        )
    )
    assert liveness is not None
    assert liveness.provider == "stub"
    assert liveness.provider_reference.startswith("STUB-LIVE-")
    assert liveness.status == "verified"


async def test_cannot_submit_identity_before_acceptance(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)

    with pytest.raises(service.InvalidTransitionError):
        await service.submit_identity_check(session, agreement.id, build_submission())


async def test_decline_closes_the_instrument(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)

    result = await service.sign_instrument(
        session, agreement.id, build_signature(accepted=False), now=NOW + timedelta(hours=1)
    )

    assert result.status is AgreementStatus.DECLINED
    assert result.closed_at is not None
    assert result.signed_at is None


async def test_trigger_then_no_further_moves(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await activate(session, agreement.id)

    triggered = await service.trigger_instrument(
        session, agreement.id, reason="Client reported a no-show.", now=NOW + timedelta(days=2)
    )
    assert triggered.status is AgreementStatus.TRIGGERED
    assert triggered.triggered_at == NOW + timedelta(days=2)

    with pytest.raises(service.InvalidTransitionError):
        await service.revoke_instrument(session, agreement.id, reason="Too late.", now=NOW)


async def test_claim_resolves_through_dispute_to_paid(
    session: AsyncSession, worker: Worker
) -> None:
    """A disputed claim is a waypoint: it still has to be paid or dismissed."""

    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await activate(session, agreement.id)
    await service.trigger_instrument(session, agreement.id, reason="No-show.", now=NOW)

    disputed = await service.resolve_claim(
        session, agreement.id, outcome="disputed", reason="Worker contests it.", now=NOW
    )
    assert disputed.status is AgreementStatus.DISPUTED
    assert disputed.resolved_at is None

    paid = await service.resolve_claim(
        session,
        agreement.id,
        outcome="paid",
        reason="Settled with the client.",
        now=NOW + timedelta(days=1),
    )
    assert paid.status is AgreementStatus.PAID
    assert paid.resolved_at == NOW + timedelta(days=1)
    assert paid.status_reason == "Settled with the client."


async def test_claim_can_be_dismissed_outright(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await activate(session, agreement.id)
    await service.trigger_instrument(session, agreement.id, reason="No-show.", now=NOW)

    dismissed = await service.resolve_claim(
        session, agreement.id, outcome="dismissed", reason="Client withdrew.", now=NOW
    )

    assert dismissed.status is AgreementStatus.DISMISSED
    # Nothing moves out of a resolved claim.
    with pytest.raises(service.InvalidTransitionError):
        await service.resolve_claim(
            session, agreement.id, outcome="paid", reason="Too late.", now=NOW
        )


async def test_cannot_resolve_a_guarantee_that_was_never_triggered(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await activate(session, agreement.id)

    with pytest.raises(service.InvalidTransitionError):
        await service.resolve_claim(
            session, agreement.id, outcome="paid", reason="Nothing to pay.", now=NOW
        )


async def test_unknown_outcome_is_refused(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    await activate(session, agreement.id)
    await service.trigger_instrument(session, agreement.id, reason="No-show.", now=NOW)

    with pytest.raises(service.UnknownOutcomeError):
        await service.resolve_claim(
            session, agreement.id, outcome="ignored", reason="?", now=NOW
        )


async def test_cannot_trigger_before_activation(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)

    with pytest.raises(service.InvalidTransitionError):
        await service.trigger_instrument(session, agreement.id, reason="Too early.", now=NOW)

    # Still not live while waiting on identity verification.
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)
    with pytest.raises(service.InvalidTransitionError):
        await service.trigger_instrument(session, agreement.id, reason="Too early.", now=NOW)


async def test_revoke_from_pending_and_active(session: AsyncSession, worker: Worker) -> None:
    pending = await service.create_instrument(session, build_request(worker), now=NOW)
    revoked = await service.revoke_instrument(
        session, pending.id, reason="Worker withdrew the request.", now=NOW
    )
    assert revoked.status is AgreementStatus.REVOKED
    assert revoked.status_reason == "Worker withdrew the request."

    active = await service.create_instrument(session, build_request(worker), now=NOW)
    await activate(session, active.id)
    assert (
        await service.revoke_instrument(session, active.id, reason="Fraud review.", now=NOW)
    ).status is AgreementStatus.REVOKED


async def test_expiry_sweep_closes_due_instruments(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(
        session, build_request(worker, valid_until=NOW + timedelta(days=1)), now=NOW
    )

    expired = await service.expire_due_instruments(session, now=NOW + timedelta(days=2))

    assert [record.id for record in expired] == [agreement.id]
    assert agreement.status is AgreementStatus.EXPIRED
    assert agreement.closed_at == NOW + timedelta(days=2)


async def test_expiry_sweep_leaves_live_instruments_alone(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)

    assert await service.expire_due_instruments(session, now=NOW + timedelta(days=1)) == []
    assert agreement.status is AgreementStatus.PENDING_SIGNATURE


async def test_signing_after_expiry_expires_instead(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(
        session, build_request(worker, valid_until=NOW + timedelta(days=1)), now=NOW
    )
    late = NOW + timedelta(days=3)

    with pytest.raises(service.InvalidTransitionError):
        await service.sign_instrument(session, agreement.id, build_signature(at=late), now=late)

    assert agreement.status is AgreementStatus.EXPIRED
    assert await session.scalar(
        select(ElectronicSignature).where(ElectronicSignature.agreement_id == agreement.id)
    ) is None


async def test_missing_instrument_raises(session: AsyncSession, worker: Worker) -> None:
    with pytest.raises(service.InstrumentNotFoundError):
        await service.get_instrument(session, worker.id)


async def test_list_filters_by_worker_and_status(session: AsyncSession, worker: Worker) -> None:
    pending = await service.create_instrument(session, build_request(worker), now=NOW)
    signed = await service.create_instrument(session, build_request(worker), now=NOW)
    await activate(session, signed.id)

    everything = await service.list_instruments(session, worker_id=worker.id)
    assert {record.id for record in everything} == {pending.id, signed.id}

    active_only = await service.list_instruments(
        session, worker_id=worker.id, statuses=[AgreementStatus.ACTIVE]
    )
    assert [record.id for record in active_only] == [signed.id]


async def test_lifecycle_writes_audit_trail(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(
        session, build_request(worker), as_draft=True, now=NOW
    )
    await service.send_for_signature(session, agreement.id, now=NOW)
    await activate(session, agreement.id)
    await service.trigger_instrument(session, agreement.id, reason="Damage claim.", now=NOW)
    await session.flush()

    events = await session.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_id == agreement.id)
        .order_by(AuditEvent.created_at)
    )
    assert {event.action for event in events} == {
        "guarantor.created",
        "guarantor.sent_for_signature",
        "guarantor.signed",
        "guarantor.identity_submitted",
        "guarantor.identity_verified",
        "guarantor.triggered",
    }

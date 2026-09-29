"""Purpose: Verify guarantor instrument lifecycle rules and signature capture.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.guarantor.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AgreementStatus, AuditEvent, ElectronicSignature, Worker
from app.schemas.api import (
    GuarantorDetails,
    GuarantorInstrumentCreateRequest,
    GuarantorRelationship,
    GuarantorSignRequest,
    SignatureMetadata,
)
from app.services import guarantor as service

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


async def test_sign_activates_and_stores_evidence(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)
    signed_at = NOW + timedelta(hours=1)

    result = await service.sign_instrument(
        session, agreement.id, build_signature(at=signed_at), now=signed_at
    )

    assert result.status is AgreementStatus.ACTIVE
    assert result.signed_at == signed_at

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
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)

    triggered = await service.trigger_instrument(
        session, agreement.id, reason="Client reported a no-show.", now=NOW + timedelta(days=2)
    )
    assert triggered.status is AgreementStatus.TRIGGERED
    assert triggered.triggered_at == NOW + timedelta(days=2)

    with pytest.raises(service.InvalidTransitionError):
        await service.revoke_instrument(session, agreement.id, reason="Too late.", now=NOW)


async def test_cannot_trigger_before_signature(session: AsyncSession, worker: Worker) -> None:
    agreement = await service.create_instrument(session, build_request(worker), now=NOW)

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
    await service.sign_instrument(session, active.id, build_signature(), now=NOW)
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
    await service.sign_instrument(session, signed.id, build_signature(), now=NOW)

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
    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW)
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
        "guarantor.triggered",
    }

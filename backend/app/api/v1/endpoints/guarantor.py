"""Purpose: Expose guarantor instrument CRUD and the signing lifecycle over HTTP.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.guarantor, and app.schemas.api.
Used by: the guarantor flow UI and platform integrations.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.domain import AgreementStatus, GuarantorAgreement, User
from app.schemas.api import (
    GuarantorInstrumentCreateRequest,
    GuarantorInstrumentCreateResponse,
    GuarantorInstrumentListResponse,
    GuarantorInstrumentResponse,
    GuarantorRevokeRequest,
    GuarantorSignRequest,
    GuarantorSignResponse,
    GuarantorSummary,
    GuarantorTriggerRequest,
    GuarantorVerifyRequest,
)
from app.services import guarantor as guarantor_service
from app.services.guarantor import (
    GuarantorError,
    InstrumentNotFoundError,
    InvalidTransitionError,
    SelfGuaranteeError,
    ValidityWindowError,
    WorkerNotFoundError,
)

router = APIRouter(prefix="/guarantor-instruments", tags=["guarantor"])


async def _to_response(
    session: AsyncSession, agreement: GuarantorAgreement
) -> GuarantorInstrumentResponse:
    person = await session.get(User, agreement.guarantor_user_id)
    return GuarantorInstrumentResponse(
        instrument_id=agreement.id,
        worker_id=agreement.worker_id,
        guarantor=GuarantorSummary(
            full_name=person.display_name if person else "",
            relationship=agreement.relationship_type,
            phone=agreement.guarantor_phone or None,
            email=person.email if person else None,
        ),
        scope=agreement.scope,
        conditions=agreement.conditions,
        status=guarantor_service.status_label(agreement.status),
        signed_at=agreement.signed_at,
        valid_until=agreement.valid_until,
        job_id=agreement.job_id,
        verified_at=agreement.verified_at,
        triggered_at=agreement.triggered_at,
        status_reason=agreement.status_reason,
        created_at=agreement.created_at,
    )


def _http_error(error: GuarantorError) -> HTTPException:
    """Map a lifecycle failure onto the status code that describes it."""

    if isinstance(error, InstrumentNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, WorkerNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, InvalidTransitionError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, (SelfGuaranteeError, ValidityWindowError)):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


@router.post(
    "",
    response_model=GuarantorInstrumentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a guarantor instrument",
)
async def create_instrument(
    payload: GuarantorInstrumentCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentCreateResponse:
    try:
        agreement = await guarantor_service.create_instrument(
            session, payload, as_draft=payload.as_draft
        )
    except GuarantorError as error:
        raise _http_error(error) from error

    await session.commit()
    return GuarantorInstrumentCreateResponse(
        instrument_id=agreement.id,
        status=guarantor_service.status_label(agreement.status),
        worker_id=agreement.worker_id,
        guarantor_name=payload.guarantor.full_name,
        created_at=agreement.created_at,
        sign_url=f"/guarantor/{agreement.id}/sign",
    )


@router.get("", response_model=GuarantorInstrumentListResponse, summary="List guarantor instruments")
async def list_instruments(
    worker_id: UUID | None = Query(default=None),
    instrument_status: AgreementStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentListResponse:
    agreements = await guarantor_service.list_instruments(
        session,
        worker_id=worker_id,
        statuses=[instrument_status] if instrument_status else None,
    )
    return GuarantorInstrumentListResponse(
        items=[await _to_response(session, agreement) for agreement in agreements]
    )


@router.get(
    "/{instrument_id}",
    response_model=GuarantorInstrumentResponse,
    summary="Fetch one guarantor instrument",
)
async def get_instrument(
    instrument_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    try:
        agreement = await guarantor_service.get_instrument(session, instrument_id)
    except GuarantorError as error:
        raise _http_error(error) from error

    return await _to_response(session, agreement)


@router.post(
    "/{instrument_id}/send",
    response_model=GuarantorInstrumentResponse,
    summary="Send a draft instrument for signature",
)
async def send_for_signature(
    instrument_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    try:
        agreement = await guarantor_service.send_for_signature(session, instrument_id)
    except GuarantorError as error:
        raise _http_error(error) from error

    await session.commit()
    return await _to_response(session, agreement)


@router.post(
    "/{instrument_id}/sign",
    response_model=GuarantorSignResponse,
    summary="Record the guarantor's signature",
)
async def sign_instrument(
    instrument_id: UUID,
    payload: GuarantorSignRequest,
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorSignResponse:
    try:
        agreement = await guarantor_service.sign_instrument(session, instrument_id, payload)
    except GuarantorError as error:
        # The expiry path records the new status before refusing the signature.
        await session.commit()
        raise _http_error(error) from error

    await session.commit()
    return GuarantorSignResponse(
        instrument_id=agreement.id,
        status=guarantor_service.status_label(agreement.status),
        signed_at=agreement.signed_at or agreement.closed_at,
    )


@router.post(
    "/{instrument_id}/verify",
    response_model=GuarantorInstrumentResponse,
    summary="Record identity verification and activate the guarantee",
)
async def verify_identity(
    instrument_id: UUID,
    payload: GuarantorVerifyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    try:
        agreement = await guarantor_service.verify_identity(
            session,
            instrument_id,
            provider=payload.provider,
            provider_reference=payload.provider_reference,
        )
    except GuarantorError as error:
        raise _http_error(error) from error

    await session.commit()
    return await _to_response(session, agreement)


@router.post(
    "/{instrument_id}/trigger",
    response_model=GuarantorInstrumentResponse,
    summary="Trigger an active guarantee",
)
async def trigger_instrument(
    instrument_id: UUID,
    payload: GuarantorTriggerRequest,
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    try:
        agreement = await guarantor_service.trigger_instrument(
            session, instrument_id, reason=payload.reason
        )
    except GuarantorError as error:
        raise _http_error(error) from error

    await session.commit()
    return await _to_response(session, agreement)


@router.post(
    "/{instrument_id}/revoke",
    response_model=GuarantorInstrumentResponse,
    summary="Revoke a guarantor instrument",
)
async def revoke_instrument(
    instrument_id: UUID,
    payload: GuarantorRevokeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    try:
        agreement = await guarantor_service.revoke_instrument(
            session, instrument_id, reason=payload.reason
        )
    except GuarantorError as error:
        raise _http_error(error) from error

    await session.commit()
    return await _to_response(session, agreement)

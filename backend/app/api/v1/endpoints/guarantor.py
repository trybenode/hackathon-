"""Purpose: Expose guarantor instrument CRUD and the signing lifecycle over HTTP.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.guarantor, and app.schemas.api.
Used by: the guarantor flow UI and platform integrations.

Who may call what:
- Platforms (platform key): create, list, send, trigger, resolve and revoke.
  Creating needs the worker's approval to write (import_history); listing a
  worker needs approval to read. Only the platform that asked for a
  guarantee may change it. Sandbox changes are answered but never kept.
- The guarantor's link: fetch and sign by the instrument's id.
- The signed-in guarantor: identity details and the liveness check.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.core.platform_auth import require_platform_api_key, require_tenant_scope
from app.db.session import get_db_session
from app.models.domain import AgreementStatus, GuarantorAgreement, Job, User, Worker
from app.models.portability import PlatformKey
from app.schemas.api import (
    GuarantorInstrumentCreateRequest,
    GuarantorInstrumentCreateResponse,
    GuarantorIdentityResponse,
    GuarantorInstrumentListResponse,
    GuarantorInstrumentResponse,
    GuarantorResolveRequest,
    GuarantorRevokeRequest,
    GuarantorSignRequest,
    GuarantorSignResponse,
    GuarantorSummary,
    GuarantorTriggerRequest,
    WorkerProfileSummary,
)
from app.services import guarantor as guarantor_service
from app.services import sandbox
from app.services.platform_history import authorize_worker
from app.services.document_store import (
    DocumentStorageError,
    DocumentTooLargeError,
    UnsupportedDocumentError,
)
from app.services.identity_provider import IdentitySubmission, LivenessSubmission
from app.services.guarantor import (
    GuarantorError,
    UnknownOutcomeError,
    IdentityCheckFailedError,
    IdentityCheckMissingError,
    LivenessCheckFailedError,
    InstrumentNotFoundError,
    InvalidTransitionError,
    InviteClaimedError,
    SelfGuaranteeError,
    UnclaimedInviteError,
    WorkerNotFoundError,
)

router = APIRouter(prefix="/guarantor-instruments", tags=["guarantor"])


async def _worker_summary(
    session: AsyncSession, agreement: GuarantorAgreement
) -> WorkerProfileSummary | None:
    """Build the worker card shown to a guarantor reviewing a request."""

    worker = await session.get(Worker, agreement.worker_id)
    if worker is None:
        return None

    person = await session.get(User, worker.user_id)
    job = await session.get(Job, agreement.job_id) if agreement.job_id else None
    return WorkerProfileSummary(
        worker_id=worker.id,
        full_name=person.display_name if person else "",
        role=worker.role,
        location=worker.location,
        avatar_url=worker.avatar_url,
        job_title=job.title if job else None,
    )


async def _to_response(
    session: AsyncSession, agreement: GuarantorAgreement
) -> GuarantorInstrumentResponse:
    person = (
        await session.get(User, agreement.guarantor_user_id)
        if agreement.guarantor_user_id
        else None
    )
    return GuarantorInstrumentResponse(
        instrument_id=agreement.id,
        worker_id=agreement.worker_id,
        worker=await _worker_summary(session, agreement),
        guarantor=GuarantorSummary(
            full_name=(person.display_name if person else "") or agreement.guarantor_name or "",
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
        resolved_at=agreement.resolved_at,
        status_reason=agreement.status_reason,
        created_at=agreement.created_at,
        claimed=agreement.guarantor_user_id is not None,
    )


def _http_error(error: GuarantorError) -> HTTPException:
    """Map a lifecycle failure onto the status code that describes it."""

    if isinstance(error, InstrumentNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, WorkerNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (InvalidTransitionError, UnclaimedInviteError, InviteClaimedError)):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, (SelfGuaranteeError, UnknownOutcomeError)):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, IdentityCheckFailedError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, LivenessCheckFailedError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, IdentityCheckMissingError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


async def _platform_write(session: AsyncSession, principal: PlatformKey, build):
    """Run a platform's change. Sandbox changes are answered, never kept."""

    if principal.environment == sandbox.SANDBOX:
        savepoint = await session.begin_nested()
        try:
            return await build()
        finally:
            await savepoint.rollback()
    response = await build()
    await session.commit()
    return response


async def _owned(session: AsyncSession, principal: PlatformKey, instrument_id: UUID) -> GuarantorAgreement:
    """The instrument, if this platform is the one that asked for it."""

    agreement = await session.get(GuarantorAgreement, instrument_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail=f"No guarantor instrument with id {instrument_id}.")
    if agreement.organization_id != principal.organization_id:
        raise HTTPException(status_code=403, detail="Only the platform that asked for this guarantee can change it.")
    return agreement


async def _as_guarantor(session: AsyncSession, user: User, instrument_id: UUID) -> None:
    """Identity and liveness belong to the guarantor named on the request."""

    agreement = await session.get(GuarantorAgreement, instrument_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail=f"No guarantor instrument with id {instrument_id}.")
    if agreement.guarantor_user_id != user.id:
        raise HTTPException(status_code=403, detail="Sign in as the guarantor named on this request.")


@router.post(
    "",
    response_model=GuarantorInstrumentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a guarantor instrument",
)
async def create_instrument(
    payload: GuarantorInstrumentCreateRequest,
    principal: PlatformKey = Depends(require_tenant_scope("guarantees")),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentCreateResponse:
    """Ask a person to stand behind a worker who approved this platform to write."""

    await authorize_worker(session, principal, payload.worker_id, "import_history")

    async def build() -> GuarantorInstrumentCreateResponse:
        try:
            agreement = await guarantor_service.create_instrument(
                session, payload, as_draft=payload.as_draft
            )
        except GuarantorError as error:
            raise _http_error(error) from error
        agreement.organization_id = principal.organization_id
        await session.flush()
        return GuarantorInstrumentCreateResponse(
            instrument_id=agreement.id,
            status=guarantor_service.status_label(agreement.status),
            worker_id=agreement.worker_id,
            guarantor_name=payload.guarantor.full_name,
            created_at=agreement.created_at,
            sign_url=f"/guarantor/{agreement.id}/sign",
        )

    return await _platform_write(session, principal, build)


@router.post(
    "/expire-due",
    summary="Expire instruments whose validity period has ended",
)
async def expire_due(
    _principal: PlatformKey | None = Depends(require_platform_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    """Run the expiry sweep on demand.

    The app also sweeps on a timer; this exists so an external scheduler can
    own it instead, and so the sweep can be triggered in a demo.
    """

    expired = await guarantor_service.expire_due_instruments(session)
    await session.commit()
    return {"expired": len(expired)}


@router.get("", response_model=GuarantorInstrumentListResponse, summary="List guarantor instruments")
async def list_instruments(
    worker_id: UUID | None = Query(default=None),
    instrument_status: AgreementStatus | None = Query(default=None, alias="status"),
    principal: PlatformKey = Depends(require_tenant_scope("guarantees")),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentListResponse:
    """A worker's guarantees, with their approval to read; without a worker,
    the guarantees this platform asked for."""

    if worker_id is not None:
        await authorize_worker(session, principal, worker_id, "read_history")
    agreements = await guarantor_service.list_instruments(
        session,
        worker_id=worker_id,
        statuses=[instrument_status] if instrument_status else None,
    )
    if worker_id is None:
        agreements = [item for item in agreements if item.organization_id == principal.organization_id]
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
    principal: PlatformKey = Depends(require_tenant_scope("guarantees")),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    await _owned(session, principal, instrument_id)

    async def build() -> GuarantorInstrumentResponse:
        try:
            agreement = await guarantor_service.send_for_signature(session, instrument_id)
        except GuarantorError as error:
            raise _http_error(error) from error
        return await _to_response(session, agreement)

    return await _platform_write(session, principal, build)


@router.post(
    "/{instrument_id}/claim",
    response_model=GuarantorInstrumentResponse,
    summary="Become the guarantor on an invite link",
)
async def claim_invite(
    instrument_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    """The signed-in person takes the invite a worker sent them."""

    try:
        agreement = await guarantor_service.claim_invite(session, instrument_id, user)
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
    "/{instrument_id}/identity",
    response_model=GuarantorIdentityResponse,
    summary="Submit the guarantor's identity details for verification",
)
async def submit_identity(
    instrument_id: UUID,
    first_name: str = Form(..., max_length=160),
    last_name: str = Form(..., max_length=160),
    phone: str = Form(..., max_length=40),
    address: str = Form(..., max_length=500),
    nin: str = Form(..., max_length=20),
    bvn: str = Form(..., max_length=20),
    utility_bill: UploadFile | None = File(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorIdentityResponse:
    """Forward identity details to the provider and keep only references.

    The utility bill goes to object storage; the database keeps its key. The
    identity numbers are passed to the provider and dropped.
    """

    await _as_guarantor(session, user, instrument_id)
    document: tuple[str, bytes] | None = None
    if utility_bill is not None and utility_bill.filename:
        document = (utility_bill.filename, await utility_bill.read())
        await utility_bill.close()

    submission = IdentitySubmission(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone.strip(),
        address=address.strip(),
        nin=nin.strip(),
        bvn=bvn.strip(),
    )

    try:
        record = await guarantor_service.submit_identity_check(
            session, instrument_id, submission, document=document
        )
    except (UnsupportedDocumentError, DocumentTooLargeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except DocumentStorageError as error:
        # The upload runs before anything is saved, so a retry starts clean.
        raise HTTPException(
            status_code=503, detail="We could not upload your document. Try again in a moment."
        ) from error
    except GuarantorError as error:
        # The failed attempt is still worth recording.
        await session.commit()
        raise _http_error(error) from error

    await session.commit()
    return GuarantorIdentityResponse(
        instrument_id=instrument_id,
        check_type=record.check_type,
        status=record.status,
        provider_reference=record.provider_reference,
    )


@router.post(
    "/{instrument_id}/liveness",
    response_model=GuarantorInstrumentResponse,
    summary="Check the liveness capture and activate the guarantee",
)
async def complete_liveness(
    instrument_id: UUID,
    frame: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    """Pass the captured frame to the liveness provider and drop it.

    The image is never stored: only the provider's reference and outcome are
    written against the guarantor.
    """

    await _as_guarantor(session, user, instrument_id)
    image = await frame.read()
    await frame.close()

    try:
        agreement = await guarantor_service.complete_liveness_check(
            session,
            instrument_id,
            LivenessSubmission(image=image, content_type=frame.content_type or "image/jpeg"),
        )
    except GuarantorError as error:
        # A failed attempt is still recorded.
        await session.commit()
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
    principal: PlatformKey = Depends(require_tenant_scope("guarantees")),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    await _owned(session, principal, instrument_id)

    async def build() -> GuarantorInstrumentResponse:
        try:
            agreement = await guarantor_service.trigger_instrument(
                session, instrument_id, reason=payload.reason
            )
        except GuarantorError as error:
            raise _http_error(error) from error
        return await _to_response(session, agreement)

    return await _platform_write(session, principal, build)


@router.post(
    "/{instrument_id}/resolve",
    response_model=GuarantorInstrumentResponse,
    summary="Record how a triggered claim ended",
)
async def resolve_claim(
    instrument_id: UUID,
    payload: GuarantorResolveRequest,
    principal: PlatformKey = Depends(require_tenant_scope("guarantees")),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    await _owned(session, principal, instrument_id)

    async def build() -> GuarantorInstrumentResponse:
        try:
            agreement = await guarantor_service.resolve_claim(
                session, instrument_id, outcome=payload.outcome, reason=payload.reason
            )
        except GuarantorError as error:
            raise _http_error(error) from error
        return await _to_response(session, agreement)

    return await _platform_write(session, principal, build)


@router.post(
    "/{instrument_id}/revoke",
    response_model=GuarantorInstrumentResponse,
    summary="Revoke a guarantor instrument",
)
async def revoke_instrument(
    instrument_id: UUID,
    payload: GuarantorRevokeRequest,
    principal: PlatformKey = Depends(require_tenant_scope("guarantees")),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInstrumentResponse:
    await _owned(session, principal, instrument_id)

    async def build() -> GuarantorInstrumentResponse:
        try:
            agreement = await guarantor_service.revoke_instrument(
                session, instrument_id, reason=payload.reason
            )
        except GuarantorError as error:
            raise _http_error(error) from error
        return await _to_response(session, agreement)

    return await _platform_write(session, principal, build)

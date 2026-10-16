"""Thin ownership-bound history routes and request-scoped recipient verification."""
from uuid import UUID
from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response, UploadFile, File, Form
import shutil
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.endpoints.auth import current_user
from app.core.config import get_settings
from app.core.history_http import history_guard
from app.db.session import get_db_session
from app.models.domain import Job, JobStatus, User
from app.models.history import ConfirmationRequest, CustomerResponse, HistoryClaim, HistoryDraft, HistoryMessage
from app.schemas.history import ChallengeView, ClaimCreate, ClaimEdit, ClaimPage, ClaimView, CodeCheck, CustomerDecision, RecipientView, RequestCreate, RequestPage, RequestView, ResponseReceipt
from app.schemas.portability import ApiError, CustomerJob, CustomerJobPage
from app.services import auth, history
from app.services import history_drafts
from app.services import history_messages, history_speech, speech_provider
from app.schemas.history import AudioView, SpeechCapabilities, MessageCreate, MessageView, MessagePage, TranslationRequest, TranslationView
from app.schemas.history import DraftView, DraftApproval, Language, HistoryCapabilities, DescriptionTranslation
from app.services.history_ai import HistoryModelGateway
from app.services.portability import FeatureError, audit, now, own_worker

router = APIRouter(tags=["work history"], dependencies=[Depends(history_guard)], responses={code: {"model": ApiError} for code in (401,403,404,409,410,422,429,503)})
SESSION = "history_recipient"


async def optional_customer(guarantor_session: str | None = Cookie(None), session: AsyncSession = Depends(get_db_session)) -> User | None:
    """Read existing account sessions without creating or extending account login."""
    return await auth.resolve_session(session, guarantor_session) if guarantor_session else None



@router.get("/me/history-capabilities", response_model=HistoryCapabilities)
async def capabilities(user: User = Depends(current_user)) -> HistoryCapabilities:
    cfg = get_settings()
    external_audio = bool(cfg.history_external_worker and cfg.history_audio_storage == "s3" and cfg.history_audio_bucket)
    local_audio = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    return HistoryCapabilities(
        voice_configured=bool(cfg.history_ai_enabled and cfg.history_ai_base_url and (external_audio or local_audio)),
        audio_max_bytes=(3 if cfg.deployment_mode == "serverless" else 5) * 1024 * 1024,
        translation_configured=bool(cfg.history_ai_enabled and cfg.history_ai_base_url),
        sms_sandbox=cfg.sms_provider == "stub",
    )


@router.get("/me/history-claims/{claim_id}/messages", response_model=MessagePage)
async def worker_messages(claim_id: UUID, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> MessagePage:
    row = await history_messages.owner_thread(session, user, claim_id)
    return await history_messages.messages(session, row.id, page, size)


@router.post("/me/history-claims/{claim_id}/messages", response_model=MessageView, status_code=201)
async def worker_send(claim_id: UUID, payload: MessageCreate, operation: UUID = Header(alias="Idempotency-Key"), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> MessageView:
    row = await history_messages.owner_thread(session, user, claim_id, lock=True)
    result = await history_messages.send(session, row, "worker", user.id, payload, operation)
    await session.commit()
    return result


@router.post("/me/history-claims/{claim_id}/messages/{message_id}/translations", response_model=TranslationView)
async def worker_translate(claim_id: UUID, message_id: UUID, payload: TranslationRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> TranslationView:
    row = await history_messages.owner_thread(session, user, claim_id)
    result = await history_messages.translate_message(session, row.id, message_id, payload.target)
    await session.commit()
    return result


@router.get("/history-confirmations/{token}/messages", response_model=MessagePage)
async def recipient_messages(token: str, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> MessagePage:
    row, claim = await history.lookup_request(session, token)
    await history.authorize(session, row, claim, user, guest)
    return await history_messages.messages(session, row.id, page, size)


@router.post("/history-confirmations/{token}/messages", response_model=MessageView, status_code=201)
async def recipient_send(token: str, payload: MessageCreate, operation: UUID = Header(alias="Idempotency-Key"), user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> MessageView:
    row, claim = await history.lookup_request(session, token, lock=True)
    await history.authorize(session, row, claim, user, guest)
    result = await history_messages.send(session, row, "customer", user.id if claim.job_id else None, payload, operation)
    await session.commit()
    return result


@router.post("/history-confirmations/{token}/messages/{message_id}/translations", response_model=TranslationView)
async def recipient_translate(token: str, message_id: UUID, payload: TranslationRequest, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> TranslationView:
    row, claim = await history.lookup_request(session, token)
    await history.authorize(session, row, claim, user, guest)
    result = await history_messages.translate_message(session, row.id, message_id, payload.target)
    row, claim = await history.lookup_request(session, token)
    await history.authorize(session, row, claim, user, guest)
    await session.commit()
    return result


@router.post("/history-confirmations/{token}/description-translation", response_model=DescriptionTranslation)
async def description_translation(token: str, payload: TranslationRequest, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> DescriptionTranslation:
    row, claim = await history.lookup_request(session, token)
    await history.authorize(session, row, claim, user, guest)
    gateway = HistoryModelGateway()
    text = await gateway.translate(row.snapshot["description"], row.snapshot["language"], payload.target)
    await session.refresh(row); await session.refresh(claim)
    row, claim = await history.lookup_request(session, token)
    await history.authorize(session, row, claim, user, guest)
    if row.revoked_at or claim.revision != row.revision or claim.archived_at:
        raise FeatureError(410, "LINK_UNAVAILABLE", "This request is no longer available.")
    return DescriptionTranslation(text=text, target=payload.target, model="NCAIR1/N-ATLaS", model_revision=gateway.translation_revision)


@router.post("/me/history-drafts", response_model=DraftView, status_code=202)
async def voice_draft(audio: UploadFile = File(), language: Language = Form(), consent: bool = Form(), job_id: UUID | None = Form(None), operation: UUID = Header(alias="Idempotency-Key"), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> DraftView:
    if not consent:
        raise FeatureError(422, "AUDIO_CONSENT_REQUIRED", "Temporary audio processing requires your approval.")
    data = await audio.read(5 * 1024 * 1024 + 1)
    result = await history_drafts.enqueue(session, user, data, language, job_id, operation)
    await session.commit()
    return result


@router.get("/me/history-drafts/{draft_id}", response_model=DraftView)
async def draft(draft_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> DraftView:
    result = history_drafts.view(await history_drafts.owned_draft(session, user, draft_id))
    await session.commit()
    return result


@router.post("/me/history-drafts/{draft_id}/retry", response_model=DraftView)
async def retry_draft(draft_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> DraftView:
    row = await history_drafts.owned_draft(session, user, draft_id, lock=True)
    if row.status != "failed" or row.attempts >= 3 or not row.audio_path:
        raise FeatureError(409, "DRAFT_RETRY_UNAVAILABLE", "Upload a new recording or enter text.")
    HistoryModelGateway()
    row.status = "queued"; row.error_code = None
    await session.commit()
    return history_drafts.view(row)


@router.post("/me/history-drafts/{draft_id}/save", response_model=ClaimView)
async def save_draft(draft_id: UUID, payload: DraftApproval, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> ClaimView:
    result = await history_drafts.approve(session, user, draft_id, payload)
    await session.commit()
    return result




@router.get("/me/history-jobs", response_model=CustomerJobPage)
async def jobs(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> CustomerJobPage:
    worker = await own_worker(session, user)
    where = (Job.worker_id == worker.id, Job.status.in_([JobStatus.COMPLETED, JobStatus.RELEASED]))
    total = await session.scalar(select(func.count()).select_from(Job).where(*where)) or 0
    rows = (await session.scalars(select(Job).where(*where).order_by(Job.created_at.desc(), Job.id).offset((page-1)*size).limit(size))).all()
    return CustomerJobPage(items=[CustomerJob(id=r.id, title=r.title, status=r.status.value, created_at=r.created_at) for r in rows], total=total, page=page, size=size, pages=(total+size-1)//size)


@router.post("/me/history-claims", response_model=ClaimView, status_code=201)
async def create(payload: ClaimCreate, operation: UUID = Header(alias="Idempotency-Key"), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> ClaimView:
    result = await history.create_claim(session, user, payload, operation)
    await session.commit()
    return result


@router.get("/me/history-claims", response_model=ClaimPage)
async def listing(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> ClaimPage:
    return await history.claims(session, user, page, size)


@router.get("/me/history-claims/{claim_id}", response_model=ClaimView)
async def detail(claim_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> ClaimView:
    return await history.claim_view(session, await history.owned_claim(session, user, claim_id))


@router.patch("/me/history-claims/{claim_id}", response_model=ClaimView)
async def edit(claim_id: UUID, payload: ClaimEdit, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> ClaimView:
    result = await history.edit_claim(session, user, claim_id, payload)
    await session.commit()
    return result


@router.delete("/me/history-claims/{claim_id}", status_code=204)
async def archive(claim_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> None:
    await history.archive_claim(session, user, claim_id)
    await session.commit()


@router.post("/me/history-claims/{claim_id}/confirmation-requests", response_model=RequestView, status_code=201)
async def issue(claim_id: UUID, payload: RequestCreate, operation: UUID = Header(alias="Idempotency-Key"), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> RequestView:
    result = await history.issue_request(session, user, claim_id, payload, operation)
    await session.commit()
    return result


@router.get("/me/history-claims/{claim_id}/confirmation-requests", response_model=RequestPage)
async def requests(claim_id: UUID, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> RequestPage:
    return await history.request_list(session, user, claim_id, page, size)


@router.get("/me/history-claims/{claim_id}/confirmation-requests/operations/{operation_id}", response_model=RequestView)
async def request_operation(claim_id: UUID, operation_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> RequestView:
    await history.owned_claim(session, user, claim_id)
    row = await session.scalar(select(ConfirmationRequest).where(ConfirmationRequest.claim_id == claim_id, ConfirmationRequest.operation_id == operation_id))
    if row is None:
        raise FeatureError(404, "OPERATION_NOT_FOUND", "This request has not completed. Retry using the same operation.")
    return await history.request_view(session, row)


@router.delete("/me/confirmation-requests/{request_id}", status_code=204)
async def revoke(request_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> None:
    row = await history.owned_request(session, user, request_id)
    row.revoked_at = row.revoked_at or now()
    row.session_hash = None
    audit(session, user.id, "history_request", row.id, "revoked")
    await session.commit()


@router.get("/history-confirmations/{token}", response_model=RecipientView)
async def recipient(token: str, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> RecipientView:
    row, claim = await history.lookup_request(session, token)
    try:
        method, sandbox = await history.authorize(session, row, claim, user, guest)
    except FeatureError as error:
        if error.code not in {"CONTACT_VERIFICATION_REQUIRED", "CUSTOMER_ACCOUNT_REQUIRED"}:
            raise
        return RecipientView(id=row.id, expires_at=row.expires_at, access="account_required" if claim.job_id else "contact_required", masked_phone=("••••"+row.recipient_phone[-4:]) if row.recipient_phone else None)
    response = await session.scalar(select(CustomerResponse).where(CustomerResponse.request_id == row.id))
    identity_status = None
    if claim.job_id:
        from app.services.worker_record import latest_check, check_status
        identity_status = check_status(await latest_check(session, user.id))
    return RecipientView(identity_status=identity_status, id=row.id, expires_at=row.expires_at, access="authorized", details=row.snapshot, attribution=response.attribution if response and not response.withdrawn_at else method, sandbox=sandbox, response=history.receipt(response) if response else None)


@router.post("/history-confirmations/{token}/challenge", response_model=ChallengeView)
async def challenge(token: str, session: AsyncSession = Depends(get_db_session)) -> ChallengeView:
    sandbox, code = await history.start_challenge(session, token)
    await session.commit()
    return ChallengeView(sandbox=sandbox, debug_code=code)


@router.post("/history-confirmations/{token}/challenge/check", response_model=ChallengeView)
async def check(token: str, payload: CodeCheck, response: Response, session: AsyncSession = Depends(get_db_session)) -> ChallengeView:
    try:
        secret = await history.check_challenge(session, token, payload.code)
    except FeatureError:
        # Failed attempts must commit, so another request cannot reset the limit.
        await session.commit()
        raise
    await session.commit()
    response.set_cookie(SESSION, secret, max_age=1800, httponly=True, secure=get_settings().environment != "development", samesite="lax", path=f"{get_settings().api_v1_prefix}/history-confirmations")
    return ChallengeView(sandbox=get_settings().sms_provider == "stub")


@router.post("/history-confirmations/{token}/response", response_model=ResponseReceipt)
async def respond(token: str, payload: CustomerDecision, request: Request, operation: UUID = Header(alias="Idempotency-Key"), user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> ResponseReceipt:
    result = await history.submit_response(session, token, user, guest, payload, operation, request.client.host if request.client else "unknown", request.headers.get("user-agent", ""))
    await session.commit()
    return result


@router.delete("/history-confirmations/{token}/response", status_code=204)
async def withdraw(token: str, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> None:
    row, claim = await history.lookup_request(session, token, lock=True)
    await history.authorize(session, row, claim, user, guest)
    response = await session.scalar(select(CustomerResponse).where(CustomerResponse.request_id == row.id))
    if response:
        response.withdrawn_at = response.withdrawn_at or now()
        audit(session, response.actor_id, "history_response", response.id, "withdrawn")
    await session.commit()


@router.get("/me/history-claims/operations/{operation_id}", response_model=ClaimView)
async def claim_operation(operation_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> ClaimView:
    """Read an owned creation receipt before retrying an uncertain write."""
    worker = await own_worker(session, user)
    row = await session.scalar(select(HistoryClaim).where(HistoryClaim.worker_id == worker.id, HistoryClaim.operation_id == operation_id))
    if row is None:
        raise FeatureError(404, "OPERATION_NOT_FOUND", "This creation has not completed. Retry the same operation.")
    return await history.claim_view(session, row)


@router.get("/me/history-drafts/operations/{operation_id}", response_model=DraftView)
async def draft_operation(operation_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> DraftView:
    """Recover a queued upload independently of current provider availability."""
    worker = await own_worker(session, user)
    row = await session.scalar(select(HistoryDraft).where(HistoryDraft.worker_id == worker.id, HistoryDraft.operation_id == operation_id))
    if row is None:
        raise FeatureError(404, "OPERATION_NOT_FOUND", "This upload has not completed. Retry the same operation.")
    result = history_drafts.view(await history_drafts.owned_draft(session, user, row.id))
    await session.commit()
    return result


async def message_operation(session: AsyncSession, request_id: UUID, role: str, operation_id: UUID) -> MessageView:
    """Resolve one authorized participant's message receipt without searching other threads."""
    row = await session.scalar(select(HistoryMessage).where(HistoryMessage.request_id == request_id, HistoryMessage.actor_role == role, HistoryMessage.operation_id == operation_id))
    if row is None:
        raise FeatureError(404, "OPERATION_NOT_FOUND", "This message has not completed. Retry the same operation.")
    return await history_messages.message_view(session, row)


@router.get("/me/history-claims/{claim_id}/messages/operations/{operation_id}", response_model=MessageView)
async def worker_message_operation(claim_id: UUID, operation_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> MessageView:
    row = await history_messages.owner_thread(session, user, claim_id)
    return await message_operation(session, row.id, "worker", operation_id)


@router.get("/history-confirmations/{token}/messages/operations/{operation_id}", response_model=MessageView)
async def recipient_message_operation(token: str, operation_id: UUID, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> MessageView:
    row, claim = await history.lookup_request(session, token)
    await history.authorize(session, row, claim, user, guest)
    return await message_operation(session, row.id, "customer", operation_id)


@router.get("/me/history-speech-capabilities", response_model=SpeechCapabilities)
async def worker_speech_capabilities(user: User = Depends(current_user)) -> SpeechCapabilities:
    languages = speech_provider.supported_languages()
    return SpeechCapabilities(languages=languages, enabled=bool(languages))


@router.get("/history-confirmations/{token}/speech-capabilities", response_model=SpeechCapabilities)
async def recipient_speech_capabilities(token: str, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> SpeechCapabilities:
    row, claim = await history.lookup_request(session, token)
    await history.authorize(session, row, claim, user, guest)
    languages = speech_provider.supported_languages()
    return SpeechCapabilities(languages=languages, enabled=bool(languages))


@router.post("/me/history-claims/{claim_id}/messages/{message_id}/audio", response_model=AudioView, status_code=202)
async def worker_audio_create(claim_id: UUID, message_id: UUID, payload: TranslationRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> AudioView:
    request = await history_messages.owner_thread(session, user, claim_id, lock=True)
    result = await history_speech.enqueue(session, request.id, message_id, payload.target, user.id)
    await session.commit()
    return result


@router.get("/me/history-claims/{claim_id}/messages/{message_id}/audio/{audio_id}", response_model=AudioView)
async def worker_audio_status(claim_id: UUID, message_id: UUID, audio_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> AudioView:
    request = await history_messages.owner_thread(session, user, claim_id)
    row = await history_speech.authorized_audio(session, request.id, message_id, audio_id)
    result = history_speech.view(row)
    await session.commit()
    return result


@router.get("/me/history-claims/{claim_id}/messages/{message_id}/audio/{audio_id}/content", response_class=Response, responses={200: {"content": {"audio/mpeg": {"schema": {"type": "string", "format": "binary"}}}}})
async def worker_audio_content(claim_id: UUID, message_id: UUID, audio_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> Response:
    request = await history_messages.owner_thread(session, user, claim_id)
    row = await history_speech.authorized_audio(session, request.id, message_id, audio_id)
    data = await history_speech.content(row)
    await session.commit()
    return Response(data, media_type="audio/mpeg", headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"})


@router.post("/history-confirmations/{token}/messages/{message_id}/audio", response_model=AudioView, status_code=202)
async def recipient_audio_create(token: str, message_id: UUID, payload: TranslationRequest, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> AudioView:
    request, claim = await history.lookup_request(session, token, lock=True)
    await history.authorize(session, request, claim, user, guest)
    result = await history_speech.enqueue(session, request.id, message_id, payload.target, user.id if user else None)
    await session.commit()
    return result


@router.get("/history-confirmations/{token}/messages/{message_id}/audio/{audio_id}", response_model=AudioView)
async def recipient_audio_status(token: str, message_id: UUID, audio_id: UUID, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> AudioView:
    request, claim = await history.lookup_request(session, token)
    await history.authorize(session, request, claim, user, guest)
    row = await history_speech.authorized_audio(session, request.id, message_id, audio_id)
    result = history_speech.view(row)
    await session.commit()
    return result


@router.get("/history-confirmations/{token}/messages/{message_id}/audio/{audio_id}/content", response_class=Response, responses={200: {"content": {"audio/mpeg": {"schema": {"type": "string", "format": "binary"}}}}})
async def recipient_audio_content(token: str, message_id: UUID, audio_id: UUID, user: User | None = Depends(optional_customer), guest: str | None = Cookie(None, alias=SESSION), session: AsyncSession = Depends(get_db_session)) -> Response:
    request, claim = await history.lookup_request(session, token)
    await history.authorize(session, request, claim, user, guest)
    row = await history_speech.authorized_audio(session, request.id, message_id, audio_id)
    data = await history_speech.content(row)
    await session.commit()
    return Response(data, media_type="audio/mpeg", headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"})

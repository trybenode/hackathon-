"""Strict contracts for unscored work declarations and scoped recipient access."""
from datetime import datetime
from typing import Literal
from uuid import UUID
import re
from pydantic import Field, model_validator, ConfigDict
from app.schemas.api import ApiModel as BaseApiModel


class ApiModel(BaseApiModel):
    model_config = ConfigDict(extra="forbid")

Language = Literal["en", "yo", "ha", "ig"]


class ClaimDetails(ApiModel):
    work_type: str = Field(min_length=1, max_length=200, pattern=r"\S")
    description: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    date_text: str | None = Field(default=None, max_length=100)
    general_area: str | None = Field(default=None, max_length=160)
    claimed_completed: bool = True
    language: Language = "en"


class ClaimCreate(ApiModel):
    details: ClaimDetails
    job_id: UUID | None = None


class ClaimEdit(ApiModel):
    revision: int = Field(ge=1)
    details: ClaimDetails


class ResponseReceipt(ApiModel):
    declares_customer: bool
    id: UUID
    decision: str
    attribution: str
    sandbox: bool
    submitted_at: datetime
    withdrawn_at: datetime | None


class ClaimView(ApiModel):
    id: UUID
    job_id: UUID | None
    revision: int
    details: ClaimDetails
    created_at: datetime
    archived_at: datetime | None
    response: ResponseReceipt | None = None


class ClaimPage(ApiModel):
    items: list[ClaimView]
    total: int
    page: int
    size: int
    pages: int


class RequestCreate(ApiModel):
    revision: int = Field(ge=1)
    recipient_phone: str | None = None

    @model_validator(mode="after")
    def valid_phone(self) -> "RequestCreate":
        if self.recipient_phone and not re.fullmatch(r"\+[1-9][0-9]{7,14}", self.recipient_phone):
            raise ValueError("Use an international phone number, e.g. +2348012345678")
        return self


class RequestView(ApiModel):
    id: UUID
    claim_id: UUID
    operation_id: UUID
    revision: int
    expires_at: datetime
    revoked_at: datetime | None
    token: str | None = None
    response: ResponseReceipt | None = None


class RequestPage(ApiModel):
    items: list[RequestView]
    total: int
    page: int
    size: int
    pages: int


class RecipientView(ApiModel):
    identity_status: Literal["verified", "sandbox", "not_verified"] | None = None
    id: UUID
    expires_at: datetime
    access: Literal["contact_required", "account_required", "authorized"]
    masked_phone: str | None = None
    details: ClaimDetails | None = None
    attribution: str | None = None
    sandbox: bool = False
    response: ResponseReceipt | None = None


class CodeCheck(ApiModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class ChallengeView(ApiModel):
    sent: bool = True
    sandbox: bool
    debug_code: str | None = None


class CustomerDecision(ApiModel):
    decision: Literal["confirmed", "incorrect", "unrecognized"]
    declares_customer: bool
    consent: Literal[True]


class InformalHistoryCounts(ApiModel):
    declared_jobs: int = 0
    contact_attested_jobs: int = 0
    sandbox_attested_jobs: int = 0
    matched_customer_jobs: int = 0
    affects_assessment: Literal[False] = False


class DraftView(ApiModel):
    id: UUID
    status: str
    language: Language
    job_id: UUID | None
    transcript: str | None
    details: ClaimDetails | None
    model_metadata: dict
    error_code: str | None
    expires_at: datetime
    claim_id: UUID | None


class DraftApproval(ApiModel):
    details: ClaimDetails
    approved: Literal[True]


class MessageCreate(ApiModel):
    text: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    language: Language


class TranslationRequest(ApiModel):
    target: Language


class TranslationView(ApiModel):
    model_revision: str | None = None
    target: Language
    status: str
    text: str | None
    model: str
    error_code: str | None


class MessageView(ApiModel):
    id: UUID
    operation_id: UUID
    actor_role: str
    language: Language
    text: str
    created_at: datetime
    translations: list[TranslationView] = Field(default_factory=list)


class MessagePage(ApiModel):
    items: list[MessageView]
    total: int
    page: int
    size: int
    pages: int


class HistoryCapabilities(ApiModel):
    voice_configured: bool
    audio_max_bytes: int = 5 * 1024 * 1024
    translation_configured: bool
    sms_sandbox: bool
    live_chat_enabled: Literal[False] = False
    translation_review: Literal["pending"] = "pending"
    spoken_prompt_review: Literal["pending"] = "pending"


class DescriptionTranslation(ApiModel):
    model_revision: str | None = None
    text: str
    target: Language
    model: str
    machine_translation: Literal[True] = True


class AudioView(ApiModel):
    """Speech status without storage paths or bearer secrets."""
    id: UUID
    language: Language
    status: Literal["queued", "processing", "ready", "failed", "expired"]
    model: str
    version: str
    expires_at: datetime
    error_code: str | None = None


class SpeechCapabilities(ApiModel):
    languages: list[Language]
    enabled: bool
    review: str = "pending"

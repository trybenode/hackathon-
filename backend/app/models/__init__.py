"""Purpose: Register and re-export all ORM models for metadata discovery.

Dependencies: app.models.domain.
Used by: Alembic autogeneration and application imports.
"""

from app.models.domain import (
	AuditEvent,
	Credential,
	CredentialTransfer,
	Dispute,
	ElectronicSignature,
	EscrowTransaction,
	GuarantorAgreement,
	LoginCode,
	UserSession,
	IdentityVerification,
	InsurancePolicy,
	Job,
	JobConfirmation,
	NormalizedOutcome,
	Organization,
	OutcomeSource,
	PlatformConnection,
	ProviderOperation,
	RawOutcome,
	TrustAssessment,
	TrustAssessmentSignal,
	TrustPolicy,
	TrustPolicyRule,
	User,
	Worker,
)

from app.models.portability import (HistoryIdentity, ImportReceipt, PlatformGrant, PlatformKey, Review, ShareGrant, WorkerLink)
from app.models.history import HistoryClaim, ConfirmationRequest, CustomerResponse, HistoryDraft, HistoryMessage, MessageTranslation, MessageAudio

__all__ = [
    "HistoryIdentity",
    "ImportReceipt",
    "PlatformGrant",
    "PlatformKey",
    "Review",
    "ShareGrant",
    "WorkerLink",
	"AuditEvent",
	"Credential",
	"CredentialTransfer",
	"Dispute",
	"ElectronicSignature",
	"EscrowTransaction",
	"GuarantorAgreement",
	"LoginCode",
	"UserSession",
	"IdentityVerification",
	"InsurancePolicy",
	"Job",
	"JobConfirmation",
	"NormalizedOutcome",
	"Organization",
	"OutcomeSource",
	"PlatformConnection",
	"ProviderOperation",
	"RawOutcome",
	"TrustAssessment",
	"TrustAssessmentSignal",
	"TrustPolicy",
	"TrustPolicyRule",
	"User",
	"Worker",
]

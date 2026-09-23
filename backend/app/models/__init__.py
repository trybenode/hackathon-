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

__all__ = [
	"AuditEvent",
	"Credential",
	"CredentialTransfer",
	"Dispute",
	"ElectronicSignature",
	"EscrowTransaction",
	"GuarantorAgreement",
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

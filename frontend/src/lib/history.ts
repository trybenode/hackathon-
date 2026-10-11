/** Unscored history and request-scoped customer attribution contracts. */
export type Language = "en" | "yo" | "ha" | "ig";
export type Details = { work_type: string; description: string; date_text: string | null; general_area: string | null; claimed_completed: boolean; language: Language };
export type Receipt = { declares_customer: boolean; id: string; decision: string; attribution: string; sandbox: boolean; submitted_at: string; withdrawn_at: string | null };
export type Claim = { id: string; job_id: string | null; revision: number; details: Details; created_at: string; archived_at: string | null; response: Receipt | null };
export type Confirmation = { id: string; claim_id: string; operation_id: string; revision: number; token: string | null; expires_at: string; revoked_at: string | null; response: Receipt | null };
export type Recipient = { identity_status?: "verified" | "sandbox" | "not_verified" | null; id: string; access: "authorized" | "account_required" | "contact_required"; masked_phone: string | null; details: Details | null; attribution: string | null; sandbox: boolean; response: Receipt | null; expires_at: string };
export type HistoryCounts = { declared_jobs: number; contact_attested_jobs: number; sandbox_attested_jobs: number; matched_customer_jobs: number; affects_assessment: false };

/** Render expiry/audit times consistently for the Nigerian pilot. */
export function historyDate(value: string, language: Language): string {
  return new Intl.DateTimeFormat(`${language}-NG`, { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Lagos" }).format(new Date(value));
}

/** Typed additional verification client; preserves signed imports and uses existing session-cookie requests. */
import { featureRequest } from "./portability";
export type Onboarding = {
  action:
    | "additional_verification"
    | "manual_review"
    | "limited"
    | "approved"
    | "declined";
  requirements: string[];
  reason_codes: string[];
  review_message: string | null;
  case_id: string | null;
  case_version: number | null;
  policy_version: number;
  evidence_revision: string;
  expires_at: string | null;
  restrictions: {
    max_active_jobs: number;
    max_job_value: string;
    currency: "NGN";
  } | null;
  next_steps: string[];
};
export type ImportBatch = {
  id: string;
  version: number;
  source_name: string;
  state: string;
  row_count: number;
  document_present: boolean;
  expires_at: string;
  last_reason: string | null;
  rows: Record<string, string>[];
  ownership_label: string;
};
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
};
export type Provisional = {
  rating: number | null;
  count: number;
  label: string;
  verified: false;
};
export type Capabilities = {
  unsigned_imports_enabled: boolean;
  additional_verification_enabled: boolean;
  csv_max_bytes: number;
  document_max_bytes: number;
  max_rows: number;
};
export type Role = { scope: string; environment: "production" | "sandbox" };
export type ReviewCase = {
  id: string;
  worker_id: string;
  display_name: string;
  version: number;
  state: string;
  last_reason: string | null;
  worker_response: string | null;
  assessment: {
    band: string;
    decision: boolean;
    confidence: number;
    score: number | null;
    explanation_summary: string;
    signals_used: string[];
  };
  verification: { identity: string; liveness: string; guarantor: string };
  platform_type: string;
  onboarding: Onboarding | null;
  provisional: Provisional;
};
export type ImportDetail = {
  batch: ImportBatch;
  worker: {
    id: string;
    name: string;
    email: string;
    profile_phone: string | null;
    identity_reference?: {
      id: string;
      provider: string;
      reference: string;
      checked_at: string;
    } | null;
    identity: string;
    liveness: string;
  };
};
export type Policy = {
  version: number;
  settings: {
    enabled: boolean;
    allow_limited: boolean;
    allow_approved: boolean;
    approval_days: number;
    restrictions: {
      max_active_jobs: number;
      max_job_value: string;
      currency: "NGN";
    };
  };
};
export const getCapabilities = () =>
  featureRequest<Capabilities>("/me/verification-capabilities");
export const getOnboarding = (
  organizationId?: string,
  platformType: PolicyType = "generic",
) =>
  featureRequest<Onboarding | null>(
    `/me/additional-verification?platform_type=${platformType}${organizationId ? `&organization_id=${encodeURIComponent(organizationId)}` : ""}`,
  );
export const submitCase = (
  organization_id?: string,
  response?: string,
  platformType: PolicyType = "generic",
) =>
  featureRequest<Onboarding>("/me/additional-verification/cases", {
    method: "POST",
    body: JSON.stringify({
      organization_id: organization_id || null,
      platform_type: platformType,
      response: response || null,
    }),
  });
export const listImports = (page = 1) =>
  featureRequest<Page<ImportBatch>>(`/me/history-imports?page=${page}&size=20`);
export const getImport = (id: string) =>
  featureRequest<ImportBatch>(`/me/history-imports/${id}`);
export const importReceipt = (operation: string) =>
  featureRequest<ImportBatch>(`/me/history-imports/operations/${operation}`);
export function prepareImport(
  file: File,
  source: string,
  operation: string,
  replaces?: string,
) {
  const body = new FormData();
  body.set("csv_file", file);
  body.set("source_name", source);
  if (replaces) body.set("replaces_id", replaces);
  return featureRequest<ImportBatch>("/me/history-imports", {
    method: "POST",
    headers: { "Idempotency-Key": operation },
    body,
  });
}
export function attachDocument(id: string, file: File) {
  const body = new FormData();
  body.set("document", file);
  return featureRequest<ImportBatch>(`/me/history-imports/${id}/document`, {
    method: "PUT",
    body,
  });
}
export const submitImport = (batch: ImportBatch) =>
  featureRequest<ImportBatch>(`/me/history-imports/${batch.id}/submit`, {
    method: "POST",
    body: JSON.stringify({ version: batch.version }),
  });
export const withdrawImport = (batch: ImportBatch) =>
  featureRequest<ImportBatch>(`/me/history-imports/${batch.id}/withdraw`, {
    method: "POST",
    body: JSON.stringify({ version: batch.version }),
  });
export const reviewAccess = () =>
  featureRequest<{ roles: Role[] }>("/review/access");
export const ownershipQueue = (page = 1) =>
  featureRequest<Page<ImportBatch>>(`/review/imports?page=${page}&size=20`);
export const ownershipDetail = (id: string) =>
  featureRequest<ImportDetail>(`/review/imports/${id}`);
export const caseQueue = (role: Role, page = 1) =>
  featureRequest<Page<ReviewCase>>(
    `/review/onboarding/${role.scope === "operations" ? "first_party" : role.scope}?environment=${role.environment}&page=${page}&size=20`,
  );
export const decideReview = <T>(
  kind: "imports" | "onboarding-cases",
  id: string,
  version: number,
  decision: string,
  reason: string,
  ownership_basis?: string,
) =>
  featureRequest<T>(`/review/${kind}/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({
      version,
      decision,
      reason,
      ownership_basis: ownership_basis || null,
    }),
  });
export const getPolicy = (role: Role, platformType: PolicyType = "generic") =>
  featureRequest<Policy>(
    `/review/policies/${role.scope}/${platformType}?environment=${role.environment}`,
  );
export const savePolicy = (
  role: Role,
  policy: Policy,
  platformType: PolicyType = "generic",
) =>
  featureRequest<Policy>(
    `/review/policies/${role.scope}/${platformType}?environment=${role.environment}`,
    { method: "PUT", body: JSON.stringify(policy) },
  );

export type PolicyType = "generic" | "domestic" | "ride_hailing";

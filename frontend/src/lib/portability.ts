/** Typed, session-scoped API access. Platform keys never enter the browser. */
import { apiBaseUrl } from "./api";
export type TrustBand = "High" | "Medium" | "Low" | "Building History";
export type Assessment = {
  decision: boolean;
  band: TrustBand;
  confidence: number;
  status: string;
  explanation_summary: string;
  signals_used: string[];
  policy: string;
  assessed_at: string;
};
export type VerificationSummary = {
  display_name: string;
  role: string | null;
  location: string | null;
  identity: { status: "verified" | "sandbox" | "not_verified" };
  assessment: Assessment;
  verified_outcomes: number;
  self_declared_outcomes: number;
  completed_jobs: number;
  completion_rate: number | null;
  active_guarantor: boolean;
  guarantor_sandbox: boolean;
  updated_at: string;
};
export type HistoryItem = {
  outcome_id: string;
  source_record_id: string;
  source_platform: string;
  source_name: string | null;
  occurred_at: string;
  status: string;
  rating: number | null;
  verified: boolean;
  verification_method: string | null;
  verified_by_org_id: string | null;
  verified_at: string | null;
  available_signals: string[] | null;
};
export type WorkerRecord = VerificationSummary & {
  worker_id: string;
  outcomes: HistoryItem[];
  total_outcomes: number;
  starting_rating: number | null;
  starting_rating_label: string | null;
};
export type Grant = {
  id: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  token: string | null;
  organization_id: string | null;
  organization_name: string | null;
  permissions: string[] | null;
};
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
};
export type ReviewReceipt = {
  id: string;
  job_id: string;
  rating: number;
  submitted_at: string;
};
export type ReviewEligibility = {
  job_id: string;
  job_title: string;
  eligible: boolean;
  reasons: string[];
  sandbox_identity: boolean;
  existing_review: ReviewReceipt | null;
};
export type CredentialBundle = {
  credential_token: string;
  exported_at: string;
  worker_id: string;
  verified_outcomes: unknown[];
  trust_summary: {
    band: TrustBand;
    confidence: number;
    total_jobs: number;
    completion_rate: number;
  };
};

export class ApiFailure extends Error {
  constructor(
    message: string,
    public status = 0,
    public code = "CONNECTION_FAILED",
    public retryAfter: number | null = null,
  ) {
    super(message);
  }
}

export async function featureRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      credentials: "include",
      cache: "no-store",
      signal: controller.signal,
      headers: {
        ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
    if (response.status === 204) return undefined as T;
    const body = await response.json();
    if (!response.ok) {
      const message =
        response.status === 401
          ? "Your session is unavailable or expired. Sign in through your existing account, then retry."
          : typeof body.detail === "string"
            ? body.detail
            : "Check your input and try again.";
      throw new ApiFailure(
        message,
        response.status,
        body.code,
        response.headers.get("Retry-After")
          ? Number(response.headers.get("Retry-After"))
          : null,
      );
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiFailure) throw error;
    throw new ApiFailure(
      "The connection was interrupted. Your input is preserved; check the result before retrying.",
    );
  } finally {
    clearTimeout(timer);
  }
}
export function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please retry.";
}
export function dateLabel(value: string) {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Africa/Lagos",
  });
}
export function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}
export function getWorkerRecord(page = 1) {
  return featureRequest<WorkerRecord>(`/me/worker/record?page=${page}&size=20`);
}
export function getReviewEligibility(id: string) {
  return featureRequest<ReviewEligibility>(
    `/jobs/${encodeURIComponent(id)}/review-eligibility`,
  );
}

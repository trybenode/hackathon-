/**
 * Purpose: Typed client for the developer dashboard, verification and credentials.
 * Dependencies: NEXT_PUBLIC_API_BASE_URL and the browser fetch API.
 * Used by: the developer sign-up, dashboard, KYB, credentials and profile screens.
 */

import { apiBaseUrl } from "./api";
import { ApiError } from "./guarantor";

export type ReviewStatus = "not_started" | "under_review" | "approved" | "rejected";
export type Environment = "sandbox" | "production";

export type ApiCall = {
  method: string;
  path: string;
  status_code: number;
  duration_ms: number;
  at: string;
};

export type DeveloperDashboard = {
  email: string;
  full_name: string | null;
  business_name: string | null;
  kyc_status: ReviewStatus;
  kyb_status: ReviewStatus;
  /** Why the last submission was sent back. */
  review_note: string | null;
  /** Step 1 is saved; step 2 is next. */
  identity_submitted: boolean;
  usage: {
    total_calls: number;
    successful_calls: number;
    /** The last 14 days, oldest first; quiet days are zero. */
    daily: { day: string; total: number; successful: number }[];
  };
  recent_activity: ApiCall[];
  credentials: { key_id: string | null; environment: Environment; created_at: string }[];
  name_change: { new_name: string; status: ReviewStatus } | null;
  sandbox_workers: { name: string; role: string; band: string; consent_token: string }[];
};

export type GeneratedCredentials = {
  key_id: string;
  /** Shown once; send it as X-API-Key. */
  secret: string;
  environment: Environment;
  created_at: string;
};

export const DOCUMENT_TYPES = [
  { value: "international_passport", label: "International passport" },
  { value: "national_id", label: "National ID card (NIN)" },
  { value: "drivers_licence", label: "Driver's licence" },
  { value: "voters_card", label: "Voter's card" },
];

export const BUSINESS_TYPES = [
  { value: "limited_liability_company", label: "Limited liability company" },
  { value: "business_name", label: "Registered business name" },
  { value: "other_entity", label: "Other registered entity" },
] as const;

export const NAME_CHANGE_REASONS = [
  { value: "correction", label: "Correction of spelling or error" },
  { value: "legal_change", label: "Legal name change" },
  { value: "other", label: "Other reason" },
] as const;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: isForm ? init?.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

function form(fields: Record<string, string>, file?: File | null) {
  const data = new FormData();
  Object.entries(fields).forEach(([key, value]) => data.append(key, value));
  if (file) data.append("document", file);
  return data;
}

export function getDeveloperDashboard() {
  return call<DeveloperDashboard>("/me/developer");
}

/** Step 1 of verification: the developer's identity document. */
export function submitDeveloperIdentity(fullName: string, documentType: string, document: File) {
  return call<DeveloperDashboard>("/me/developer/identity", {
    method: "POST",
    body: form({ full_name: fullName, document_type: documentType }, document),
  });
}

/** Step 2: the registered business. Sends both steps for review. */
export function submitDeveloperBusiness(
  details: { business_name: string; business_type: string; registration_number: string; tax_id: string },
  document: File,
) {
  return call<DeveloperDashboard>("/me/developer/business", {
    method: "POST",
    body: form({ ...details, confirmed: "true" }, document),
  });
}

/** The secret comes back here only. */
export function generateCredentials(environment: Environment) {
  return call<GeneratedCredentials>("/me/developer/credentials", {
    method: "POST",
    body: JSON.stringify({ environment }),
  });
}

export function requestNameChange(newName: string, reason: string, document: File | null) {
  return call<DeveloperDashboard>("/me/developer/name-change", {
    method: "POST",
    body: form({ new_name: newName, reason }, document),
  });
}

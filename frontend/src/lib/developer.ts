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
  sandbox_workers: {
    name: string;
    role: string;
    band: string;
    /** "active", "pending", "expired", or null for none. */
    guarantor: string | null;
    consent_token: string;
  }[];
};

export type AccessGroup = "trust" | "history" | "guarantees" | "scoring";

export type ApiKey = {
  id: string;
  name: string;
  /** Public; safe to show and copy. */
  key_id: string | null;
  environment: Environment;
  /** null is full access, future features included. */
  scopes: AccessGroup[] | null;
  /** Operator-approved: imported records count as verified. */
  can_attest: boolean;
  /** Waiting on an operator's attest decision. */
  attest_requested: boolean;
  created_at: string;
  last_used_at: string | null;
  /** Calls over the last 14 days. */
  recent_calls: number;
};

export type ApiKeyList = {
  items: ApiKey[];
  access_groups: { id: AccessGroup; label: string; description: string }[];
  max_active_per_environment: number;
};

/** A key with its secret, returned only when the key is made or rotated. */
export type ApiKeySecret = { key: ApiKey; secret: string };

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
  if (response.status === 204) return undefined as T;
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

export function listApiKeys() {
  return call<ApiKeyList>("/me/developer/keys");
}

/** `scopes: null` is full access. The secret comes back here only. */
export function createApiKey(name: string, environment: Environment, scopes: AccessGroup[] | null) {
  return call<ApiKeySecret>("/me/developer/keys", {
    method: "POST",
    body: JSON.stringify({ name, environment, scopes }),
  });
}

export function updateApiKey(id: string, name: string, scopes: AccessGroup[] | null) {
  return call<ApiKey>(`/me/developer/keys/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name, scopes }),
  });
}

/** A new secret for the same key; the old one stops working at once. */
export function rotateApiKey(id: string) {
  return call<ApiKeySecret>(`/me/developer/keys/${id}/rotate`, { method: "POST" });
}

/** Production keys only: ask for imported records to count as verified. */
export function requestAttest(id: string) {
  return call<ApiKey>(`/me/developer/keys/${id}/attest-request`, { method: "POST" });
}

/** Email a code to the new address, the first step of changing it. */
export function requestEmailChange(email: string) {
  return call<{ sent: boolean; debug_code: string | null }>("/auth/email-change/code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function confirmEmailChange(email: string, code: string) {
  return call<{ email: string }>("/auth/email-change", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

export function revokeApiKey(id: string) {
  return call<void>(`/me/developer/keys/${id}`, { method: "DELETE" });
}

export function requestNameChange(newName: string, reason: string, document: File | null) {
  return call<DeveloperDashboard>("/me/developer/name-change", {
    method: "POST",
    body: form({ new_name: newName, reason }, document),
  });
}

/** "pk_sandbox_a989ea**********": the prefix and first characters, the rest hidden. */
export function maskKeyId(keyId: string) {
  const match = /^(pk_(?:sandbox|live)_)(.+)$/.exec(keyId);
  if (!match) return keyId;
  const [, prefix, rest] = match;
  return `${prefix}${rest.slice(0, 6)}${"*".repeat(Math.max(rest.length - 6, 0))}`;
}

export type LogKey = { id: string; name: string; key_id: string | null; environment: Environment; revoked: boolean };

export type LogEntry = {
  at: string;
  method: string;
  /** The route template; worker ids never appear. */
  path: string;
  status_code: number;
  duration_ms: number;
  key: LogKey;
};

export type LogPage = {
  items: LogEntry[];
  total: number;
  page: number;
  size: number;
  pages: number;
  /** Every key, revoked ones too, for filtering. */
  keys: LogKey[];
};

export type LogOutcome = "all" | "success" | "error";

/** Calls made with the platform's keys, newest first. */
export function getCallLog(options: { page?: number; key?: string | null; outcome?: LogOutcome } = {}) {
  const params = new URLSearchParams({ page: String(options.page ?? 1), size: "25", outcome: options.outcome ?? "all" });
  if (options.key) params.set("key", options.key);
  return call<LogPage>(`/me/developer/logs?${params}`);
}

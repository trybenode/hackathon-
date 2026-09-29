/**
 * Purpose: Typed client for the guarantor instrument endpoints.
 * Dependencies: NEXT_PUBLIC_API_BASE_URL and the browser fetch API.
 * Used by: the guarantor create, detail, and signing screens.
 */

import { apiBaseUrl } from "./api";

export type InstrumentStatus =
  | "Draft"
  | "Pending Signature"
  | "Pending Verification"
  | "Active"
  | "Triggered"
  | "Suspended"
  | "Expired"
  | "Revoked"
  | "Declined";

export type GuarantorRelationship = "sibling" | "parent" | "spouse" | "colleague" | "other";

export type GuarantorDetails = {
  full_name: string;
  phone: string;
  email: string;
  relationship: GuarantorRelationship;
  address: string;
};

export type CreateInstrumentRequest = {
  worker_id: string;
  guarantor: GuarantorDetails;
  scope: string;
  conditions: string;
  valid_until: string;
  job_id?: string | null;
  as_draft?: boolean;
};

export type CreateInstrumentResponse = {
  instrument_id: string;
  status: InstrumentStatus;
  worker_id: string;
  guarantor_name: string;
  created_at: string;
  sign_url: string | null;
};

export type WorkerProfile = {
  worker_id: string;
  full_name: string;
  role: string | null;
  location: string | null;
  avatar_url: string | null;
  job_title: string | null;
};

export type Instrument = {
  instrument_id: string;
  worker_id: string;
  worker: WorkerProfile | null;
  guarantor: {
    full_name: string;
    relationship: string;
    phone: string | null;
    email: string | null;
  };
  scope: string;
  conditions: string;
  status: InstrumentStatus;
  signed_at: string | null;
  valid_until: string;
  job_id: string | null;
  verified_at: string | null;
  triggered_at: string | null;
  status_reason: string | null;
  created_at: string | null;
};

export type SignInstrumentRequest = {
  signer_name: string;
  signer_phone: string;
  accepted: boolean;
  signature_metadata: {
    ip: string;
    user_agent: string;
    timestamp: string;
  };
};

export type SignInstrumentResponse = {
  instrument_id: string;
  status: InstrumentStatus;
  signed_at: string;
};

/** An API error carrying the status code so callers can tell 409 from 422. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    // FastAPI puts the human-readable reason in `detail`.
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

export function createInstrument(payload: CreateInstrumentRequest) {
  return request<CreateInstrumentResponse>("/guarantor-instruments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listInstruments(params: { workerId?: string; status?: string } = {}) {
  const query = new URLSearchParams();
  if (params.workerId) query.set("worker_id", params.workerId);
  if (params.status) query.set("status", params.status);
  const suffix = query.size > 0 ? `?${query}` : "";

  return request<{ items: Instrument[] }>(`/guarantor-instruments${suffix}`);
}

export function getInstrument(instrumentId: string) {
  return request<Instrument>(`/guarantor-instruments/${instrumentId}`);
}

export function sendForSignature(instrumentId: string) {
  return request<Instrument>(`/guarantor-instruments/${instrumentId}/send`, { method: "POST" });
}

export function signInstrument(instrumentId: string, payload: SignInstrumentRequest) {
  return request<SignInstrumentResponse>(`/guarantor-instruments/${instrumentId}/sign`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type IdentityDetails = {
  first_name: string;
  last_name: string;
  phone: string;
  address: string;
  nin: string;
  bvn: string;
};

export type IdentityCheckResponse = {
  instrument_id: string;
  check_type: string;
  status: string;
  provider_reference: string;
};

/**
 * Sends identity details to the API as multipart, matching the form on the
 * identity screen. The values go straight to the KYC provider; only the
 * provider's reference is stored.
 */
export async function submitIdentity(
  instrumentId: string,
  details: IdentityDetails,
  utilityBill?: File | null,
) {
  const form = new FormData();
  Object.entries(details).forEach(([key, value]) => form.append(key, value));
  if (utilityBill) form.append("utility_bill", utilityBill);

  const response = await fetch(`${apiBaseUrl}/guarantor-instruments/${instrumentId}/identity`, {
    method: "POST",
    body: form,
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<IdentityCheckResponse>;
}

export function triggerInstrument(instrumentId: string, reason: string) {
  return request<Instrument>(`/guarantor-instruments/${instrumentId}/trigger`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function revokeInstrument(instrumentId: string, reason: string) {
  return request<Instrument>(`/guarantor-instruments/${instrumentId}/revoke`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

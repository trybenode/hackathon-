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
  | "Disputed"
  | "Paid"
  | "Dismissed"
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
    // The session is an HTTP-only cookie, so it has to ride along.
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    // FastAPI puts the human-readable reason in `detail`.
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
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
    credentials: "include",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<IdentityCheckResponse>;
}

/**
 * Posts a captured selfie frame for the liveness check. The frame goes to the
 * provider and is dropped; only the provider's reference is stored.
 */
export async function submitLiveness(instrumentId: string, frame: Blob) {
  const form = new FormData();
  form.append("frame", frame, "selfie.jpg");

  const response = await fetch(`${apiBaseUrl}/guarantor-instruments/${instrumentId}/liveness`, {
    method: "POST",
    body: form,
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<Instrument>;
}

export type ClaimOutcome = "disputed" | "paid" | "dismissed";

/** Records how a triggered claim ended. */
export function resolveClaim(instrumentId: string, outcome: ClaimOutcome, reason: string) {
  return request<Instrument>(`/guarantor-instruments/${instrumentId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ outcome, reason }),
  });
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

export type SignedInUser = {
  user_id: string;
  email: string;
  display_name: string;
};

/**
 * Asks the API to email a login code.
 *
 * `debug_code` comes back only outside production, so the flow can be tested
 * before the email provider is wired up.
 */
export function requestLoginCode(email: string) {
  return request<{ sent: boolean; debug_code: string | null }>("/auth/code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function verifyLoginCode(email: string, code: string) {
  return request<SignedInUser>("/auth/verify", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

export type Profile = {
  user_id: string;
  email: string;
  display_name: string;
  phone: string | null;
  address: string | null;
};

export function getProfile() {
  return request<Profile>("/me/profile");
}

export function updateProfile(update: {
  display_name: string;
  phone?: string | null;
  address?: string | null;
}) {
  return request<Profile>("/me/profile", {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}

export function getSignedInUser() {
  return request<SignedInUser>("/auth/me");
}

export function signOut() {
  return request<void>("/auth/logout", { method: "POST" });
}

export type GuaranteeCard = {
  instrument_id: string;
  /** Short reference to quote, e.g. "G-3F9A1C". */
  reference: string;
  worker_name: string;
  worker_role: string | null;
  avatar_url: string | null;
  job_title: string | null;
  status: string;
  /**
   * Where "My guarantees" files it. Active and Expired have tabs; guarantees
   * closed some other way (revoked, paid…) show only under All. "request"
   * never went live, so it is only on the requests screen.
   */
  bucket: "request" | "active" | "expired" | "closed";
  /** Where "Guarantee requests" files it; null for lapsed requests. */
  request_bucket: "pending" | "accepted" | "declined" | null;
  requested_at: string;
  /** When the guarantor accepted or declined. */
  responded_at: string | null;
  /** When the guarantee's year began; null until it goes live. */
  started_on: string | null;
  /** The deadline to answer a request, or the end of a guarantee's year. */
  valid_until: string;
  ended_on: string | null;
};

export type ActivityItem = {
  id: string;
  label: string;
  at: string;
  /** Present on the home screen's list, which spans every guarantee. */
  worker_name?: string;
};

export type DashboardData = {
  greeting_name: string;
  active_count: number;
  /** Requests waiting for the guarantor's answer. */
  pending_count: number;
  expired_count: number;
  guarantees: GuaranteeCard[];
  recent_activity: ActivityItem[];
  action_required: GuaranteeCard | null;
};

export type NotificationItem = {
  id: string;
  title: string;
  body: string;
  at: string;
  icon: "bell" | "check" | "calendar";
};

export type GuaranteeDetail = {
  guarantee: GuaranteeCard;
  relationship: string;
  scope: string;
  conditions: string;
  signed_at: string | null;
  activity: ActivityItem[];
  /** The agreement, one paragraph per entry. */
  agreement: string[];
};

export function getGuarantee(instrumentId: string) {
  return request<GuaranteeDetail>(`/me/guarantees/${instrumentId}`);
}

/** Fetches the agreement as a text file, for saving. */
export async function downloadAgreement(instrumentId: string) {
  const response = await fetch(`${apiBaseUrl}/me/guarantees/${instrumentId}/agreement`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) throw new ApiError(response.statusText, response.status);

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "agreement.txt";
  return { blob: await response.blob(), filename };
}

export function getDashboard() {
  return request<DashboardData>("/me/dashboard");
}

export function getNotifications() {
  return request<NotificationItem[]>("/me/notifications");
}

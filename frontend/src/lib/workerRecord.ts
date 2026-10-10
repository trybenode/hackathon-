/**
 * Purpose: Typed client for the signed-in worker's portable record.
 * Dependencies: NEXT_PUBLIC_API_BASE_URL and the browser fetch API.
 * Used by: the worker profile, portable record, outcomes and credentials screens.
 */

import { apiBaseUrl } from "./api";
import { ApiError } from "./guarantor";

export type TrustBand = "High" | "Medium" | "Low" | "Building History";

export type RecordAssessment = {
  decision: boolean;
  /** How much evidence backs the score, 0 to 1. Not the score itself. */
  confidence: number;
  /**
   * How good the record is, 0 to 1: the "Trust Score" ring, and what the band
   * is cut from. Null while the worker is still building history.
   */
  score: number | null;
  band: TrustBand;
  status: string;
  signals_used: string[];
  explanation_summary: string;
};

export type RecordOutcome = {
  id: string;
  title: string;
  occurred_at: string;
  amount: string | null;
  status: "Client Confirmed" | "Auto-released";
  location: string | null;
  client_name: string | null;
  /** The customer's 1-5 stars; null for outcomes imported from elsewhere. */
  rating: number | null;
  /** "none", or how a dispute on the job ended. */
  dispute: "none" | "dismissed" | "upheld";
  /** "native" here, else the platform it was imported from. */
  source: string;
};

export type IdentityCredential = {
  nin_verified: boolean;
  bvn_verified: boolean;
  verified_at: string;
};

export type GuarantorCredential = {
  name: string;
  verified: boolean;
  status: "Active" | "Expired";
  activated_at: string;
  /** A guarantee runs for one year from activation. */
  valid_until: string;
  /** How the guarantor knows the worker, e.g. "employer". */
  relationship: string;
};

export type ImportedRecordCredential = {
  verified_outcomes: number;
  updated_at: string;
};

/**
 * The three kinds of verified credential a worker carries between platforms
 * (SRS 3.5): identity, an active guarantor, and imported work history.
 */
export type Credentials = {
  identity: IdentityCredential | null;
  guarantor: GuarantorCredential | null;
  imported_record: ImportedRecordCredential | null;
};

export type WorkerRecord = {
  worker_id: string;
  name: string;
  role: string | null;
  avatar_url: string | null;
  identity_verified: boolean;
  assessment: RecordAssessment;
  /** Verified outcomes the assessment rests on. */
  verified_outcomes: number;
  last_updated: string;
  stats: {
    completed_jobs: number;
    /** Completed share of the jobs the worker was responsible for. */
    completion_rate: number | null;
    repeat_hires: number;
    disputes: number;
  };
  /** Completed jobs, newest first. */
  outcomes: RecordOutcome[];
  credentials: Credentials;
};

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store", credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export function getWorkerRecord() {
  return get<WorkerRecord>("/me/record");
}

/**
 * The signed export of the worker's verified history, for importing on
 * another platform.
 */
export function exportCredentials(workerId: string) {
  return get<Record<string, unknown>>(`/workers/${workerId}/credentials/export`);
}

/**
 * Bring a previously exported record back in (FR-5.2). The exported file
 * carries a signed token; the API checks the signature and that the record
 * is this worker's.
 */
export async function importCredentials(workerId: string, credentialToken: string, sourcePlatform: string) {
  const response = await fetch(`${apiBaseUrl}/workers/${workerId}/credentials/import`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential_token: credentialToken, source_platform: sourcePlatform }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<{ imported_outcomes: number; new_band: string }>;
}

/** "Jane A." from "Jane Adams", as the record shows it. */
export function shortName(name: string) {
  const [first, ...rest] = name.trim().split(/\s+/);
  const last = rest.at(-1);
  return last ? `${first} ${last[0].toUpperCase()}.` : first;
}

/** 87% */
export function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

/** ₦15,000, without the kobo the escrow screens show. Amounts arrive as strings. */
export function formatNairaWhole(amount: string | number | null) {
  if (amount === null) return "—";
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(value)) return "—";
  return `₦${value.toLocaleString("en-NG", { maximumFractionDigits: 0 })}`;
}

/** 20/2/2026 */
export function formatNumericDate(value: string) {
  const date = new Date(value);
  return `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`;
}

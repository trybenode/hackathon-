/**
 * Purpose: Typed client for the signed-in worker's escrow-protected jobs.
 * Dependencies: NEXT_PUBLIC_API_BASE_URL and the browser fetch API.
 * Used by: the worker Jobs, Job Details and Escrow screens.
 */

import { apiBaseUrl } from "./api";
import { ApiError } from "./guarantor";

/** Where a job's money stands. */
export type JobStage =
  | "awaiting_payment"
  | "held"
  | "awaiting_confirmation"
  | "disputed"
  | "released"
  | "refunded";

export type WorkerJob = {
  id: string;
  title: string;
  /** Decimal string, e.g. "25000.00". */
  amount: string;
  client_name: string | null;
  location: string | null;
  details: { label: string; value: string }[];
  stage: JobStage;
  assigned_at: string;
  completed_at: string | null;
  /** When the client was reminded to confirm. Money never moves on a timer. */
  confirmation_reminded_at: string | null;
  escrow: {
    /** Payscrow's transaction number, e.g. MKT-05893531. */
    transaction_number: string | null;
    payment_link: string | null;
    total_payable: string | null;
    funded_at: string | null;
    released_at: string | null;
    /** Micro-insurance premium the client paid on top of the job. */
    premium: string | null;
    /** Cover runs from the premium being paid until the job settles. */
    cover_active: boolean;
    dispute_stage: string | null;
    resolution_type: string | null;
  } | null;
  dispute: { id: string; reference: string; reason: string; submitted_at: string } | null;
};

/** The reasons offered on "Report an issue". */
export const ISSUE_REASONS = [
  "Client didn't provide required access",
  "Work conditions changed",
  "Client requested extra work",
  "Payment-related issue",
  "Other",
] as const;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getMyJobs() {
  return call<WorkerJob[]>("/me/jobs");
}

export function getMyJob(jobId: string) {
  return call<WorkerJob>(`/me/jobs/${jobId}`);
}

export function completeJob(jobId: string) {
  return call<WorkerJob>(`/me/jobs/${jobId}/complete`, { method: "POST" });
}

export function reportIssue(jobId: string, reason: string, complaint: string) {
  return call<WorkerJob>(`/me/jobs/${jobId}/issue`, {
    method: "POST",
    body: JSON.stringify({ reason, complaint }),
  });
}

/** Anything not yet settled is active. */
export function jobTab(job: WorkerJob): "Active" | "Completed" {
  return job.stage === "released" || job.stage === "refunded" ? "Completed" : "Active";
}

/** The card's "Job status" line. */
export function jobStatusLabel(job: WorkerJob) {
  switch (job.stage) {
    case "awaiting_payment":
      return "Awaiting payment";
    case "held":
      return "In progress";
    case "refunded":
      return "Cancelled";
    default:
      return "Completed";
  }
}

/** The card's "Payment status" line. */
export function paymentStatusLabel(job: WorkerJob) {
  switch (job.stage) {
    case "awaiting_payment":
      return "Awaiting client payment";
    case "held":
      return "Protected";
    case "awaiting_confirmation":
      return "Awaiting Confirmation";
    case "disputed":
      return "Under dispute";
    case "released":
      return "Released";
    case "refunded":
      return "Refunded to client";
  }
}

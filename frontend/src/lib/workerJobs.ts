/**
 * Purpose: Typed client for the signed-in worker's jobs.
 * Dependencies: NEXT_PUBLIC_API_BASE_URL and the browser fetch API.
 * Used by: the worker Home, Jobs and Job Details screens.
 */

import { apiBaseUrl } from "./api";
import { ApiError } from "./guarantor";

/** Where a job stands; the same stages drive the customer's page. */
export type JobStage =
  | "awaiting_customer"
  | "awaiting_payment"
  | "held"
  | "awaiting_confirmation"
  | "disputed"
  | "released"
  | "refunded";

export type DisputeInfo = {
  reference: string;
  reason: string;
  /** "customer", "worker", or "timeout" (no code within the window). */
  raised_by: string;
  /** Payscrow's stage: NegotiationOpen, EvidenceCollection, AwaitingArbiterDecision, Resolved. */
  stage: string | null;
  resolution: string | null;
  submitted_at: string;
  history: { stage: string; at: string }[];
};

export type WorkerJob = {
  id: string;
  title: string;
  /** Decimal string, e.g. "25000.00". */
  amount: string;
  address: string | null;
  scheduled_at: string | null;
  /** The link to send the customer. */
  link: string;
  stage: JobStage;
  created_at: string;
  /** The customer's details, once they have paid. */
  client_name: string | null;
  client_email: string | null;
  client_phone: string | null;
  funded_at: string | null;
  completed_at: string | null;
  released_at: string | null;
  transaction_number: string | null;
  premium: string | null;
  cover_active: boolean;
  rating: number | null;
  dispute: DisputeInfo | null;
};

/** The worker's reasons on "Report an issue". */
export const WORKER_ISSUE_REASONS = [
  "Client didn't provide required access",
  "Work conditions changed",
  "Client requested extra work",
  "Payment-related issue",
  "Other",
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

export type WorkerNotification = {
  id: string;
  job_id: string;
  title: string;
  body: string;
  at: string;
  icon: "check" | "warning";
};

export function getMyNotifications() {
  return call<WorkerNotification[]>("/me/job-notifications");
}

export function getMyJobs() {
  return call<WorkerJob[]>("/me/jobs");
}

export function getMyJob(jobId: string) {
  return call<WorkerJob>(`/me/jobs/${jobId}`);
}

export function createJob(job: { title: string; address: string; scheduled_at: string; price: string }) {
  return call<WorkerJob>("/me/jobs", { method: "POST", body: JSON.stringify(job) });
}

export function completeJob(jobId: string) {
  return call<WorkerJob>(`/me/jobs/${jobId}/complete`, { method: "POST" });
}

export function reportIssue(jobId: string, reason: string, complaint: string, evidence: File[]) {
  const form = new FormData();
  form.set("reason", reason);
  form.set("complaint", complaint);
  evidence.forEach((file) => form.append("evidence", file));
  return call<WorkerJob>(`/me/jobs/${jobId}/issue`, { method: "POST", body: form });
}

/** Anything not yet settled is active. */
export function jobTab(job: WorkerJob): "Active" | "Completed" {
  return job.stage === "released" || job.stage === "refunded" ? "Completed" : "Active";
}

/** The card's "Job status" line. */
export function jobStatusLabel(job: WorkerJob) {
  switch (job.stage) {
    case "awaiting_customer":
      return "Waiting for customer";
    case "awaiting_payment":
      return "Awaiting payment";
    case "held":
      return "In progress";
    case "disputed":
      return "In dispute";
    case "refunded":
      return "Cancelled";
    default:
      return "Completed";
  }
}

/** The card's "Payment status" line. */
export function paymentStatusLabel(job: WorkerJob) {
  switch (job.stage) {
    case "awaiting_customer":
      return "Link not paid yet";
    case "awaiting_payment":
      return "Awaiting customer payment";
    case "held":
      return "Protected";
    case "awaiting_confirmation":
      return "Awaiting Confirmation";
    case "disputed":
      return "Under dispute";
    case "released":
      return "Released";
    case "refunded":
      return "Refunded to customer";
  }
}

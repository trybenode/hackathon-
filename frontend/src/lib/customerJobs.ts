/**
 * Purpose: Typed client for the customer's job page, keyed by the job link.
 * Dependencies: NEXT_PUBLIC_API_BASE_URL and the browser fetch API.
 * Used by: /j/[token]. Customers have no account: the link's token is the key.
 */

import { apiBaseUrl } from "./api";
import { ApiError } from "./guarantor";
import type { DisputeInfo, JobStage } from "./workerJobs";
import type { TrustBand } from "./workerRecord";

export type CustomerJob = {
  title: string;
  amount: string;
  /** Job protection (micro-insurance), paid on top of the job. */
  premium: string;
  address: string | null;
  scheduled_at: string | null;
  worker: {
    name: string;
    role: string | null;
    avatar_url: string | null;
    band: TrustBand;
    score: number | null;
  };
  stage: JobStage;
  created_at: string;
  customer_name: string | null;
  /** Set until the payment is confirmed, to return to Payscrow. */
  payment_link: string | null;
  total_payable: string | null;
  funded_at: string | null;
  completed_at: string | null;
  released_at: string | null;
  /** The deadline to release or report, once the worker has completed. */
  confirm_by: string | null;
  rating: number | null;
  dispute: DisputeInfo | null;
};

/** The customer's reasons on "Report an issue". */
export const CUSTOMER_ISSUE_REASONS = [
  "Worker didn't show up or arrived late",
  "Damaged or missing items",
  "Problem with the job code",
  "Payment-related issue",
  "Other",
] as const;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const response = await fetch(`${apiBaseUrl}/public/jobs${path}`, {
    ...init,
    cache: "no-store",
    headers: isForm ? init?.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export function getCustomerJob(token: string) {
  return call<CustomerJob>(`/${token}`);
}

export function startPayment(token: string, details: { name: string; email: string; phone: string }) {
  return call<{ payment_link: string; total_payable: string }>(`/${token}/payment`, {
    method: "POST",
    body: JSON.stringify(details),
  });
}

export function releasePayment(token: string, code: string, rating: number) {
  return call<CustomerJob>(`/${token}/release`, {
    method: "POST",
    body: JSON.stringify({ code, rating }),
  });
}

export function reportCustomerIssue(token: string, reason: string, complaint: string, evidence: File[]) {
  const form = new FormData();
  form.set("reason", reason);
  form.set("complaint", complaint);
  evidence.forEach((file) => form.append("evidence", file));
  return call<CustomerJob>(`/${token}/issue`, { method: "POST", body: form });
}

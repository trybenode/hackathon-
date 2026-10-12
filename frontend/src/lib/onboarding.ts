/**
 * Purpose: Typed client for a new worker's verification steps.
 * Dependencies: NEXT_PUBLIC_API_BASE_URL and the browser fetch API.
 * Used by: the worker onboarding screens and the worker Home.
 */

import { apiBaseUrl } from "./api";
import { ApiError, type GuarantorRelationship } from "./guarantor";

export type OnboardingStep = "identity" | "liveness" | "guarantor";

export type GuarantorInvite = {
  instrument_id: string;
  name: string;
  relationship: string;
  /** "Pending Signature", "Pending Verification" or "Active". */
  status: string;
  expires_at: string;
  /** The page the worker sends their guarantor. */
  link: string;
};

export type Onboarding = {
  identity_verified: boolean;
  liveness_verified: boolean;
  /** Job links need an active guarantor. */
  guarantor: "none" | "pending" | "active";
  /** The first unfinished step; null once nothing is left. */
  next_step: OnboardingStep | null;
  invite: GuarantorInvite | null;
};

export type WorkerIdentity = {
  first_name: string;
  last_name: string;
  /** YYYY-MM-DD. */
  date_of_birth: string;
  phone: string;
  address: string;
  nin: string;
  bvn: string;
};

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

export function getOnboarding() {
  return call<Onboarding>("/me/worker/onboarding");
}

/** The numbers go to the identity provider; only its reference is stored. */
export function submitWorkerIdentity(details: WorkerIdentity, utilityBill?: File | null) {
  const form = new FormData();
  Object.entries(details).forEach(([key, value]) => form.append(key, value));
  if (utilityBill) form.append("utility_bill", utilityBill);
  return call<Onboarding>("/me/worker/identity", { method: "POST", body: form });
}

/** The frame goes to the provider and is dropped. */
export function submitWorkerLiveness(frame: Blob) {
  const form = new FormData();
  form.append("frame", frame, "selfie.jpg");
  return call<Onboarding>("/me/worker/liveness", { method: "POST", body: form });
}

/** A link for the guarantor, valid for seven days. */
export function inviteGuarantor(firstName: string, lastName: string, relationship: GuarantorRelationship) {
  return call<GuarantorInvite>("/me/worker/guarantor", {
    method: "POST",
    body: JSON.stringify({ first_name: firstName, last_name: lastName, relationship }),
  });
}

/** Translate static failure meaning; never machine-translate authorization or consent. */
import { ApiFailure, errorMessage, featureRequest } from "./portability";
import type { CopyKey } from "./historyLanguage";
export function historyError(error: unknown, t: (key: CopyKey) => string): string {
  if (!(error instanceof ApiFailure)) return errorMessage(error);
  if (error.code === "THREAD_UNAVAILABLE") return "Create a confirmation request for the current job details first. Revoked, expired or superseded requests cannot be used for clarification.";
  if (error.code === "CODE_INVALID") return t("invalidCode");
  if (error.code === "CHALLENGE_UNAVAILABLE") return t("retryCode");
  if (error.status === 0) return t("uncertain");
  if (error.status === 410) return t("linkUnavailable");
  if (error.status === 429) return t("rateLimited");
  if (error.status === 401) return t("accountRequired");
  if (error.status === 403) return t("notAllowed");
  if (error.status === 422) return t("invalidInput");
  if (error.status === 503) return t("serviceUnavailable");
  return `${t("requestRejected")} (${error.code})`;
}

export function uncertainFailure(error: unknown): boolean {
  return error instanceof ApiFailure && (error.status === 0 || error.status >= 500);
}
/** A missing receipt permits the same idempotent write; outages do not. */
export async function operationReceipt<T>(path: string): Promise<T | null> {
  try { return await featureRequest<T>(path); }
  catch (error) { if (error instanceof ApiFailure && error.status === 404 && error.code === "OPERATION_NOT_FOUND") return null; throw error; }
}

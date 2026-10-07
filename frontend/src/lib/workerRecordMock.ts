/**
 * Purpose: Placeholder profile, trust score and portable record for the worker screens.
 * Dependencies: none.
 * Used by: the worker profile and portable record routes until the trust and
 * credentials APIs exist.
 *
 * `assessment` follows the dict that trust_scoring.score_worker() returns, so
 * the screens can switch to the real /trust/query response without reshaping,
 * plus one field that dict does not have yet: `score`, which the designs show
 * as the "Trust Score" percentage.
 */

export type TrustBand = "High" | "Medium" | "Low" | "Building History";

export type TrustAssessment = {
  decision: boolean;
  /**
   * How much evidence backs the score, from 0 to 1: job count against the
   * preset's k, times the share of weighted signals present. Not a second
   * score; a worker with a poor record and plenty of jobs is low score, high
   * confidence.
   */
  confidence: number;
  /**
   * How good the worker's record is, from 0 to 1: the weighted average of the
   * normalised signals. score_worker() already computes this and derives
   * `band` (high_t / medium_t) and `decision` (baseline) from it, but does not
   * return it. Returning it, rounded, is the change these screens need.
   * Null for Building History and Disqualified, which return before scoring.
   */
  score: number | null;
  band: TrustBand;
  status: "Scored" | "Building History" | "Disqualified";
  signals_used: string[];
  explanation_summary: string;
};

export type VerifiedOutcome = {
  id: string;
  title: string;
  date: string;
  amount: number;
  status: "Client Confirmed" | "Auto-released";
};

/**
 * The verified claims a worker carries between platforms (SRS 3.5). Exactly
 * three kinds count: identity (NIN and BVN), an active guarantor, and work
 * history imported from another platform. Not documents; those stay with the
 * provider that checked them. Distinct from verified outcomes, which are
 * individual jobs on this platform.
 */
export type IdentityCredential = {
  ninVerified: boolean;
  bvnVerified: boolean;
  verifiedAt: string;
};

export type GuarantorCredential = {
  name: string;
  /** The guarantor passed their own identity checks. */
  verified: boolean;
  status: "Active" | "Expired";
  activatedAt: string;
  /** A guarantee runs for one year from activation. */
  validUntil: string;
};

export type ImportedRecordCredential = {
  verifiedOutcomes: number;
  updatedAt: string;
};

export type Credentials = {
  identity: IdentityCredential | null;
  guarantor: GuarantorCredential | null;
  importedRecord: ImportedRecordCredential | null;
};

export type WorkerRecord = {
  name: string;
  /** "Jane A." on the record, which leaves the profile for a link's viewers. */
  shortName: string;
  role: string;
  identityVerified: boolean;
  assessment: TrustAssessment;
  /** Jobs whose outcome was verified, on this platform: score_worker's n_jobs. */
  verifiedOutcomes: number;
  lastUpdated: string;
  credentials: Credentials;
  stats: {
    completedJobs: number;
    onTimeRate: number;
    repeatHires: number;
    disputes: number;
  };
  outcomes: VerifiedOutcome[];
};

/** The guarantor credential in both states the designs cover. */
export const guarantorStates: Record<"active" | "expired", GuarantorCredential> = {
  active: {
    name: "John Parker",
    verified: true,
    status: "Active",
    activatedAt: "2026-09-12T10:00:00+01:00",
    validUntil: "2027-09-12T10:00:00+01:00",
  },
  expired: {
    name: "John Parker",
    verified: true,
    status: "Expired",
    activatedAt: "2025-09-12T10:00:00+01:00",
    validUntil: "2026-09-12T10:00:00+01:00",
  },
};

const OUTCOME_HISTORY: [string, string, number, VerifiedOutcome["status"]][] = [
  ["Home cleaning", "2026-09-20", 15000, "Client Confirmed"],
  ["Deep cleaning", "2026-09-06", 40000, "Client Confirmed"],
  ["Home cleaning", "2026-08-23", 15000, "Auto-released"],
  ["Office cleaning", "2026-08-09", 50000, "Client Confirmed"],
  ["Home cleaning", "2026-07-26", 15000, "Client Confirmed"],
  ["Home cleaning", "2026-07-12", 15000, "Client Confirmed"],
  ["Deep cleaning", "2026-06-28", 40000, "Client Confirmed"],
  ["Home cleaning", "2026-06-14", 15000, "Auto-released"],
  ["Home cleaning", "2026-05-31", 15000, "Client Confirmed"],
  ["Office cleaning", "2026-05-17", 50000, "Client Confirmed"],
  ["Home cleaning", "2026-05-03", 15000, "Client Confirmed"],
  ["Home cleaning", "2026-04-19", 15000, "Client Confirmed"],
];

export const workerRecord: WorkerRecord = {
  name: "Jane Adams",
  shortName: "Jane A.",
  role: "Cleaner",
  identityVerified: true,
  assessment: {
    decision: true,
    confidence: 0.81,
    score: 0.87,
    band: "High",
    status: "Scored",
    signals_used: ["completion_rate", "dispute_rate", "no_show_rate", "repeat_hire_rate"],
    explanation_summary: "Score 0.87 vs baseline 0.60; weakest signal: dispute_rate",
  },
  verifiedOutcomes: 42,
  lastUpdated: "2026-09-23T10:00:00+01:00",
  credentials: {
    identity: { ninVerified: true, bvnVerified: true, verifiedAt: "2026-09-12T10:00:00+01:00" },
    guarantor: guarantorStates.active,
    importedRecord: { verifiedOutcomes: 42, updatedAt: "2026-10-05T10:00:00+01:00" },
  },
  stats: {
    completedJobs: 42,
    onTimeRate: 0.95,
    repeatHires: 12,
    disputes: 1,
  },
  // Newest first, as the outcome history reads.
  outcomes: OUTCOME_HISTORY.map(([title, date, amount, status], index) => ({
    id: `out-${index + 1}`,
    title,
    date,
    amount,
    status,
  })),
};

/** 87% */
export function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

/** ₦15,000, without the kobo the escrow screens show. */
export function formatNairaWhole(amount: number) {
  return `₦${amount.toLocaleString("en-NG", { maximumFractionDigits: 0 })}`;
}

/** 20/2/2026 */
export function formatNumericDate(value: string) {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return `${day}/${month}/${year}`;
}

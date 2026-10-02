/**
 * Purpose: Placeholder profile, trust score and portable record for the worker screens.
 * Dependencies: none.
 * Used by: the worker profile and portable record routes until the trust and
 * credentials APIs exist.
 *
 * `assessment` follows the dict that trust_scoring.score_worker() returns, so
 * the screens can switch to the real /trust/query response without reshaping.
 * score_worker() does not return the score itself yet; the 87% in the designs
 * needs it, so `score` is carried alongside until that output includes it.
 */

export type TrustBand = "High" | "Medium" | "Low" | "Building History";

export type TrustAssessment = {
  decision: boolean;
  confidence: number;
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

export type WorkerRecord = {
  name: string;
  /** "Jane A." on the record, which leaves the profile for a link's viewers. */
  shortName: string;
  role: string;
  identityVerified: boolean;
  score: number;
  assessment: TrustAssessment;
  /** Verified outcomes the score rests on: score_worker's n_jobs. */
  verifiedOutcomes: number;
  lastUpdated: string;
  credentials: number;
  stats: {
    completedJobs: number;
    onTimeRate: number;
    repeatHires: number;
    disputes: number;
  };
  outcomes: VerifiedOutcome[];
};

export const SHARE_SCOPES = [
  "Work outcomes",
  "Trust history",
  "Performance",
  "Identity verification",
] as const;

export type ShareScope = (typeof SHARE_SCOPES)[number];

/** Shared links stop working after this many days. */
export const SHARE_LINK_DAYS = 7;

export const workerRecord: WorkerRecord = {
  name: "Jane Adams",
  shortName: "Jane A.",
  role: "Cleaner",
  identityVerified: true,
  score: 0.87,
  assessment: {
    decision: true,
    confidence: 0.81,
    band: "High",
    status: "Scored",
    signals_used: ["completion_rate", "dispute_rate", "no_show_rate", "repeat_hire_rate"],
    explanation_summary: "Score 0.87 vs baseline 0.60; weakest signal: dispute_rate",
  },
  verifiedOutcomes: 42,
  lastUpdated: "2026-09-23T10:00:00+01:00",
  credentials: 8,
  stats: {
    completedJobs: 42,
    onTimeRate: 0.95,
    repeatHires: 12,
    disputes: 1,
  },
  outcomes: [
    { id: "out-1", title: "Home cleaning", date: "2026-02-20", amount: 15000, status: "Client Confirmed" },
    { id: "out-2", title: "Home cleaning", date: "2026-02-20", amount: 15000, status: "Client Confirmed" },
    { id: "out-3", title: "Home cleaning", date: "2026-02-20", amount: 15000, status: "Client Confirmed" },
  ],
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

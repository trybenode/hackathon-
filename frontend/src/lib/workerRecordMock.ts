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
 * A verified claim the worker carries between platforms (SRS 3.5): who they
 * are, who stands behind them, and work history verified elsewhere. Not
 * documents; the documents stay with the provider that checked them. Distinct
 * from verified outcomes, which are individual jobs on this platform.
 */
export type VerifiedCredential = {
  id: string;
  kind: "identity" | "guarantor" | "imported_history";
  label: string;
  issuer: string;
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
  credentials: VerifiedCredential[];
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
  credentials: [
    { id: "cred-1", kind: "identity", label: "Identity verified (NIN)", issuer: "KYC provider" },
    { id: "cred-2", kind: "identity", label: "Liveness check passed", issuer: "KYC provider" },
    { id: "cred-3", kind: "guarantor", label: "Active guarantor", issuer: "Guarantor instrument" },
    { id: "cred-4", kind: "imported_history", label: "12 verified jobs", issuer: "CleanPro" },
    { id: "cred-5", kind: "imported_history", label: "9 verified jobs", issuer: "HomeHelp NG" },
    { id: "cred-6", kind: "imported_history", label: "6 verified jobs", issuer: "Sparkle Services" },
    { id: "cred-7", kind: "imported_history", label: "4 verified jobs", issuer: "TidyUp" },
    { id: "cred-8", kind: "imported_history", label: "3 verified jobs", issuer: "Maids Direct" },
  ],
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

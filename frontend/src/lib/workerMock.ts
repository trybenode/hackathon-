/**
 * Purpose: Placeholder jobs and escrow states for the worker screens.
 * Dependencies: none.
 * Used by: the worker jobs and escrow routes until the job and escrow APIs exist.
 *
 * Shaped around the FR-6 / FR-7 lifecycle in the SRS: funds are held in
 * escrow, the worker marks the job complete, the client confirms (or the
 * system auto-releases), and a dispute holds the funds for review.
 */

export type EscrowStage = "held" | "awaiting_confirmation" | "disputed" | "released";

export type JobDetail = { label: string; value: string };

export type Dispute = {
  id: string;
  submittedAt: string;
  reason: string;
  complaint: string;
};

export type WorkerJob = {
  id: string;
  clientName: string;
  /** Avatar fill; the designs use a different colour per client. */
  clientTone: "cyan" | "purple";
  title: string;
  amount: number;
  location: string;
  details: JobDetail[];
  escrowStage: EscrowStage;
  escrowReference: string;
  coverageActive: boolean;
  assignedAt: string;
  startedAt: string;
  paymentReceivedAt: string;
  fundsHeldAt: string;
  completedAt: string | null;
  confirmedAt: string | null;
  releasedAt: string | null;
  dispute: Dispute | null;
};

export const ISSUE_REASONS = [
  "Client didn't provide required access",
  "Work conditions changed",
  "Client requested extra work",
  "Payment-related issue",
  "Other",
] as const;

const at = (time: string) => `2026-09-29T${time}+01:00`;

export const initialJobs: WorkerJob[] = [
  {
    id: "job-1",
    clientName: "Peter James",
    clientTone: "cyan",
    title: "Home cleaning",
    amount: 25000,
    location: "Lekki, Lagos",
    details: [
      { label: "bedrooms", value: "2" },
      { label: "Bathroom", value: "1" },
      { label: "Duration", value: "4 hours" },
      { label: "Timing", value: "flexible" },
    ],
    escrowStage: "held",
    escrowReference: "ESC-284019",
    coverageActive: true,
    assignedAt: at("12:04:32"),
    startedAt: at("12:04:32"),
    paymentReceivedAt: at("12:04:32"),
    fundsHeldAt: at("12:04:32"),
    completedAt: null,
    confirmedAt: null,
    releasedAt: null,
    dispute: null,
  },
  {
    id: "job-2",
    clientName: "John Parker",
    clientTone: "purple",
    title: "Office cleaning",
    amount: 50000,
    location: "Victoria Island, Lagos",
    details: [
      { label: "Rooms", value: "6" },
      { label: "Restrooms", value: "2" },
      { label: "Duration", value: "6 hours" },
      { label: "Timing", value: "evening" },
    ],
    escrowStage: "awaiting_confirmation",
    escrowReference: "ESC-284112",
    coverageActive: true,
    assignedAt: at("09:10:05"),
    startedAt: at("09:40:00"),
    paymentReceivedAt: at("09:10:05"),
    fundsHeldAt: at("09:10:06"),
    completedAt: at("15:42:18"),
    confirmedAt: null,
    releasedAt: null,
    dispute: null,
  },
  {
    // Not in the jobs-list frame: added so the released escrow screen has a
    // job that reaches it.
    id: "job-3",
    clientName: "Amaka Obi",
    clientTone: "cyan",
    title: "Deep cleaning",
    amount: 40000,
    location: "Ikeja, Lagos",
    details: [
      { label: "bedrooms", value: "3" },
      { label: "Bathroom", value: "2" },
      { label: "Duration", value: "8 hours" },
      { label: "Timing", value: "morning" },
    ],
    escrowStage: "released",
    escrowReference: "ESC-283950",
    coverageActive: false,
    assignedAt: at("08:00:00"),
    startedAt: at("08:15:00"),
    paymentReceivedAt: at("08:00:00"),
    fundsHeldAt: at("08:00:01"),
    completedAt: at("16:20:44"),
    confirmedAt: at("17:05:12"),
    releasedAt: at("17:05:13"),
    dispute: null,
  },
];

/** The label a job card shows for where the job is. */
export function jobStatusLabel(job: WorkerJob) {
  return job.escrowStage === "held" ? "In progress" : "Completed";
}

/** The label a job card shows for the money. */
export function paymentStatusLabel(job: WorkerJob) {
  switch (job.escrowStage) {
    case "held":
      return "Protected";
    case "awaiting_confirmation":
      return "Awaiting Confirmation";
    case "disputed":
      return "Under dispute";
    case "released":
      return "Released";
  }
}

/** Which tab a job belongs to: anything past "in progress" is completed. */
export function jobTab(job: WorkerJob): "Active" | "Completed" {
  return job.escrowStage === "held" ? "Active" : "Completed";
}

export function initialsOf(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

// Formatting helpers. lib/format.ts carries the same on the guarantor branch;
// they live here so this branch does not edit a file that one changes. Fold
// them back into lib/format.ts after that branch merges.

/** ₦25,000.00 */
export function formatNaira(amount: number) {
  return `₦${amount.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** 12:04:32 */
export function formatTime(value: string) {
  return new Date(value).toLocaleTimeString("en-GB", { hour12: false });
}

// Month names are spelled out rather than taken from the browser locale,
// which abbreviates them differently ("Sep" vs "Sept") from one runtime to
// the next. The designs use both forms, in different places.
const SHORT_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
const LONG_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"];

/** 29 sep 2026 */
export function formatShortDate(value: string) {
  const date = new Date(value);
  return `${date.getDate()} ${SHORT_MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

/** Sept 29, 2026 */
export function formatLongDate(value: string) {
  const date = new Date(value);
  return `${LONG_MONTHS[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

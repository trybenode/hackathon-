"use client";

import { useState } from "react";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { CalendarIcon, CheckIcon, LocationPinIcon, VerificationBadge, WarningTriangleIcon } from "@/components/ui";
import { formatDayMonthYear, formatNaira, initialsOf } from "@/lib/workerFormat";
import { formatNairaWhole, type RecordOutcome } from "@/lib/workerRecord";

const DISPUTE: Record<RecordOutcome["dispute"], string> = {
  none: "No dispute",
  dismissed: "Dispute dismissed",
  upheld: "Dispute upheld",
};

function Stars({ rating }: { rating: number }) {
  return (
    <span className="flex items-center gap-1" aria-label={`${rating.toFixed(1)} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <svg key={star} viewBox="0 0 24 24" width="18" height="18" aria-hidden>
          <path
            d="m12 2.6 2.9 6 6.5.8-4.8 4.5 1.2 6.5L12 17.2l-5.8 3.2 1.2-6.5L2.6 9.4l6.5-.8z"
            className={star <= Math.round(rating) ? "fill-warning" : "fill-grey-200"}
          />
        </svg>
      ))}
      <span className="ml-1 text-body-sm text-grey-900">{rating.toFixed(1)}</span>
    </span>
  );
}

/** "view verified outcome": the job, where and when, any dispute, and the client's rating. */
function OutcomeDialog({ outcome, onClose }: { outcome: RecordOutcome | null; onClose: () => void }) {
  return (
    <WorkerDialog open={outcome !== null} onClose={onClose} label="Verified outcome">
      {outcome && (
        <div className="flex flex-col gap-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <h2 className="text-body-md font-semibold text-grey-900">{outcome.title}</h2>
              <p className="text-body-sm text-grey-900">
                {outcome.amount ? formatNaira(Number(outcome.amount)) : "—"}
              </p>
            </div>
            <VerificationBadge status="verified" className="py-1 text-body-sm" />
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs leading-4 text-grey-900">
            {outcome.location && (
              <span className="flex items-center gap-1.5">
                <LocationPinIcon width={14} height={14} className="shrink-0" />
                {outcome.location}
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <CalendarIcon width={14} height={14} className="shrink-0" />
              {formatDayMonthYear(outcome.occurred_at)}
            </span>
            <span className="flex items-center gap-1.5">
              <WarningTriangleIcon width={14} height={14} className="shrink-0" />
              {DISPUTE[outcome.dispute]}
            </span>
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-stroke pt-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-pill bg-primary-500 text-body-sm text-white">
                {outcome.client_name ? initialsOf(outcome.client_name) : "?"}
              </span>
              <span className="flex flex-col">
                <span className="text-body-md text-grey-900">
                  {outcome.client_name ?? (outcome.source === "native" ? "Client" : `Via ${outcome.source}`)}
                </span>
                <span className="text-xs leading-4 text-grey-600">Client</span>
              </span>
            </div>
            {outcome.rating !== null ? (
              <Stars rating={outcome.rating} />
            ) : (
              <span className="text-xs text-grey-600">No rating</span>
            )}
          </div>
        </div>
      )}
    </WorkerDialog>
  );
}

/**
 * The "Verified outcomes" card, on the record and on the full history. Each
 * row opens the outcome with the client's rating.
 */
export function OutcomeList({ outcomes }: { outcomes: RecordOutcome[] }) {
  const [open, setOpen] = useState<RecordOutcome | null>(null);

  return (
    <div className="overflow-hidden rounded-lg bg-white shadow-1">
      <h2 className="bg-primary-25 px-3 py-4 text-body-md text-grey-900">Verified outcomes</h2>
      {outcomes.length === 0 ? (
        <p className="border-t border-stroke px-3 py-4 text-body-sm text-grey-600">No verified outcomes yet.</p>
      ) : (
        <ul>
          {outcomes.map((outcome) => (
            <li key={outcome.id} className="border-t border-stroke">
              <button
                type="button"
                onClick={() => setOpen(outcome)}
                className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-grey-50"
              >
                <CheckIcon className="shrink-0 text-grey-900" />
                <span className="flex flex-1 flex-col">
                  <span className="text-body-sm font-medium text-grey-900">{outcome.title}</span>
                  <span className="text-body-sm text-grey-800">{formatDayMonthYear(outcome.occurred_at)}</span>
                </span>
                <span className="text-body-sm text-grey-900">{formatNairaWhole(outcome.amount)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <OutcomeDialog outcome={open} onClose={() => setOpen(null)} />
    </div>
  );
}

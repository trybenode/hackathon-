import { TrustBandBadge } from "./TrustBandBadge";
import {
  dateLabel,
  percent,
  type VerificationSummary,
} from "@/lib/portability";

/** Shared private/public presentation of the standard verification summary. */
export function EvidenceSummary({ record }: { record: VerificationSummary }) {
  return (
    <section className="flex flex-col gap-5 rounded-xl border border-stroke bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-h3 font-semibold text-navy-500">
            {record.display_name}
          </h2>
          <p className="text-body-sm text-grey-600">
            {[record.role, record.location].filter(Boolean).join(" · ") ||
              "Work record"}
          </p>
        </div>
        <TrustBandBadge band={record.assessment.band} />
      </div>
      <div className="rounded-lg bg-primary-25 p-4">
        <p className="text-body-md font-medium">
          Evidence confidence: {percent(record.assessment.confidence)}
        </p>
        <p className="mt-1 text-body-sm text-grey-600">
          How much evidence supports this assessment, rather than a performance
          percentage.
        </p>
        <p className="mt-3 text-body-sm">
          {record.assessment.explanation_summary}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-4 text-body-sm">
        <div>
          <dt className="text-grey-600">Verified work records</dt>
          <dd className="text-body-lg font-semibold">
            {record.verified_outcomes}
          </dd>
        </div>
        <div>
          <dt className="text-grey-600">Self-declared records</dt>
          <dd className="text-body-lg font-semibold">
            {record.self_declared_outcomes}
          </dd>
        </div>
        <div>
          <dt className="text-grey-600">Completed verified jobs</dt>
          <dd>{record.completed_jobs}</dd>
        </div>
        <div>
          <dt className="text-grey-600">Verified completion rate</dt>
          <dd>
            {record.completion_rate === null
              ? "Building history"
              : percent(record.completion_rate)}
          </dd>
        </div>
        <div>
          <dt className="text-grey-600">Identity check</dt>
          <dd>
            {record.identity.status === "sandbox"
              ? "Sandbox check · demo"
              : record.identity.status === "verified"
                ? "Verified"
                : "Not verified"}
          </dd>
        </div>
        <div>
          <dt className="text-grey-600">Guarantor</dt>
          <dd>
            {record.active_guarantor
              ? record.guarantor_sandbox
                ? "Active · sandbox evidence"
                : "Active"
              : "No active instrument"}
          </dd>
        </div>
      </dl>
      <p className="text-xs text-grey-600">
        Policy: {record.assessment.policy} · Assessed{" "}
        {dateLabel(record.assessment.assessed_at)}
      </p>
      <p className="text-body-sm text-grey-600">
        This result describes available evidence. Viewing it does not activate
        job escrow or insurance.
      </p>
    </section>
  );
}

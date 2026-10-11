import { english, type Dictionary } from "@/lib/historyLanguage";
import { HistoryCounts } from "@/components/history/HistoryCounts";
import { TrustBandBadge } from "./TrustBandBadge";
import {
  dateLabel,
  percent,
  type VerificationSummary,
} from "@/lib/portability";

/** Shared private/public presentation of the standard verification summary. */
export function EvidenceSummary({
  record,
  dictionary = english,
}: {
  record: VerificationSummary;
  dictionary?: Dictionary;
}) {
  return (
    <section className="flex flex-col gap-5 rounded-xl border border-stroke bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-h3 font-semibold text-navy-500">
            {record.display_name}
          </h2>
          <p className="text-body-sm text-grey-600">
            {[record.role, record.location].filter(Boolean).join(" · ") ||
              dictionary.record}
          </p>
        </div>
        <TrustBandBadge band={record.assessment.band} />
      </div>
      <div className="rounded-lg bg-primary-25 p-4">
        <p className="text-body-md font-medium">
          {dictionary.confidence}: {percent(record.assessment.confidence)}
        </p>
        <p className="mt-1 text-body-sm text-grey-600">
          {dictionary.confidenceHelp}
        </p>
        <p lang="en" className="mt-3 text-body-sm">
          {record.assessment.explanation_summary}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-4 text-body-sm">
        <div>
          <dt className="text-grey-600">{dictionary.verifiedRecords}</dt>
          <dd className="text-body-lg font-semibold">
            {record.verified_outcomes}
          </dd>
        </div>
        <div>
          <dt className="text-grey-600">{dictionary.selfDeclaredRecords}</dt>
          <dd className="text-body-lg font-semibold">
            {record.self_declared_outcomes}
          </dd>
        </div>
        <div>
          <dt className="text-grey-600">{dictionary.completedVerified}</dt>
          <dd>{record.completed_jobs}</dd>
        </div>
        <div>
          <dt className="text-grey-600">{dictionary.completionRate}</dt>
          <dd>
            {record.completion_rate === null
              ? dictionary.building
              : percent(record.completion_rate)}
          </dd>
        </div>
        <div>
          <dt className="text-grey-600">{dictionary.identity}</dt>
          <dd>
            {record.identity.status === "sandbox"
              ? dictionary.sandbox
              : record.identity.status === "verified"
                ? dictionary.verified
                : dictionary.notVerified}
          </dd>
        </div>
        <div>
          <dt className="text-grey-600">{dictionary.guarantor}</dt>
          <dd>
            {record.active_guarantor
              ? record.guarantor_sandbox
                ? dictionary.sandbox
                : dictionary.active
              : dictionary.noGuarantor}
          </dd>
        </div>
      </dl>
      <HistoryCounts counts={record.informal_history} dictionary={dictionary} />
      <p className="text-xs text-grey-600">
        {dictionary.policy}: {record.assessment.policy} · {dictionary.assessed}{" "}
        {dateLabel(record.assessment.assessed_at)}
      </p>
      <p className="text-body-sm text-grey-600">{dictionary.evidenceOnly}</p>
    </section>
  );
}

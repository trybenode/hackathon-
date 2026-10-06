"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { statusDot } from "@/components/dashboard/GuaranteeCard";
import { useGuarantee } from "@/components/dashboard/useGuarantee";
import { WorkerAvatar } from "@/components/dashboard/WorkerAvatar";
import { CheckIcon, DotIcon } from "@/components/ui";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { cn } from "@/lib/cn";
import { formatActivityTime, formatLongDay } from "@/lib/format";
import type { GuaranteeCard } from "@/lib/guarantor";

/** One line under the status saying what it means for the guarantor. */
function standing(guarantee: GuaranteeCard) {
  switch (guarantee.status) {
    case "Active":
      return "You are currently guaranteeing this worker";
    case "Triggered":
    case "Disputed":
      return "A claim is open against this guarantee";
    case "Suspended":
      return "This guarantee is on hold";
    case "Expired":
      return "Your guarantee for this worker has ended";
    default:
      return guarantee.bucket === "request"
        ? "Waiting for your response"
        : `This guarantee was ${guarantee.status.toLowerCase()}`;
  }
}

/** When the guarantee runs out, or when it stopped if it already has. */
function endRow(guarantee: GuaranteeCard) {
  if (guarantee.bucket === "expired") {
    return { label: "Expired on", value: formatLongDay(guarantee.ended_on ?? guarantee.valid_until) };
  }
  if (guarantee.bucket === "closed") {
    return { label: "Ended on", value: formatLongDay(guarantee.ended_on) };
  }
  return { label: "Valid until", value: formatLongDay(guarantee.valid_until) };
}

function capitalise(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function GuaranteeDetails({ instrumentId }: { instrumentId: string }) {
  const router = useRouter();
  const { data, error, loading } = useGuarantee(instrumentId);

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Guarantee Details</h1>
      </header>

      {loading && (
        <p role="status" className="px-6 pt-8 text-body-sm text-grey-600">
          Loading…
        </p>
      )}
      {error && (
        <p role="alert" className="px-6 pt-8 text-body-sm text-error">
          {error}
        </p>
      )}

      {data && (
        <div className="flex flex-col gap-8 px-6 pt-8">
          <section className="flex flex-col gap-6 rounded-xl border border-stroke bg-white p-4 shadow-1">
            <div className="flex items-center gap-3">
              <WorkerAvatar name={data.guarantee.worker_name} src={data.guarantee.avatar_url} size={52} />
              <span className="flex flex-col">
                <span className="text-body-md text-grey-900">{data.guarantee.worker_name}</span>
                <span className="text-body-sm text-grey-600">{data.guarantee.worker_role ?? ""}</span>
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between gap-3 text-body-sm text-grey-900">
                <span className="flex items-center gap-1.5">
                  <DotIcon
                    className={cn("shrink-0", statusDot[data.guarantee.status] ?? "text-grey-400")}
                  />
                  {data.guarantee.status}
                </span>
                <span>#{data.guarantee.reference.replace("-", " - ")}</span>
              </div>
              <p className="text-body-sm text-grey-900">{standing(data.guarantee)}</p>
            </div>
          </section>

          <section className="flex flex-col px-4">
            <h2 className="pb-2 text-body-md font-medium text-grey-900">Guarantee Information</h2>
            <dl className="flex flex-col">
              {[
                { label: "Relationship", value: capitalise(data.relationship) },
                { label: "Guarantee started", value: formatLongDay(data.guarantee.started_on) },
                endRow(data.guarantee),
              ].map((row) => (
                <div
                  key={row.label}
                  className="flex items-center justify-between gap-4 border-b border-stroke py-5"
                >
                  <dt className="text-body-sm text-grey-600">{row.label}</dt>
                  <dd className="text-body-sm font-medium text-grey-900">{row.value}</dd>
                </div>
              ))}
            </dl>
          </section>

          {data.activity.length > 0 && (
            <section className="flex flex-col overflow-hidden rounded-lg bg-white shadow-1">
              <h2 className="bg-primary-25 px-3 py-4 text-body-md text-grey-900">Recent activity</h2>
              <ul className="flex flex-col">
                {data.activity.map((entry) => (
                  <li key={entry.id} className="flex items-center gap-4 border-t border-stroke px-3 py-2">
                    <CheckIcon className="shrink-0 text-grey-900" />
                    <span className="flex flex-col">
                      <span className="text-body-sm font-medium text-grey-900">{entry.label}</span>
                      <span className="text-body-sm text-grey-800">{formatActivityTime(entry.at)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <Link
            href={`/guarantor/${instrumentId}/agreement`}
            className="mb-4 flex h-12 w-52 items-center justify-center self-center rounded-xl bg-primary-500 text-body-lg font-semibold text-white transition-colors hover:bg-primary-400"
          >
            View Agreement
          </Link>
        </div>
      )}
    </main>
  );
}

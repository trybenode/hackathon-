"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { RecordGate } from "@/components/worker/RecordGate";
import { useWorkerResource } from "@/components/worker/useWorkerResource";
import { Button, DotIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import {
  getMyJobs,
  jobStatusLabel,
  jobTab,
  paymentStatusLabel,
  type WorkerJob,
} from "@/lib/workerJobs";
import { formatNaira, initialsOf } from "@/lib/workerFormat";

const TABS = ["All", "Active", "Completed"] as const;
type Tab = (typeof TABS)[number];

/** The designs give each client a different avatar colour. */
const AVATAR_TONES = ["bg-primary-400", "bg-badge-pending-text"];

function toneFor(name: string) {
  const sum = [...name].reduce((total, char) => total + char.charCodeAt(0), 0);
  return AVATAR_TONES[sum % AVATAR_TONES.length];
}

function JobCard({ job }: { job: WorkerJob }) {
  const tab = jobTab(job);

  return (
    <article className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-pill text-body-md font-medium text-white",
              toneFor(job.client_name ?? ""),
            )}
          >
            {job.client_name ? initialsOf(job.client_name) : "?"}
          </span>
          <span className="flex flex-col">
            <span className="text-body-md text-grey-900">{job.client_name ?? "Awaiting customer"}</span>
            <span className="text-body-sm text-grey-600">Client</span>
          </span>
        </div>
        <span className="flex items-center gap-1.5 text-body-sm text-grey-900">
          <DotIcon className="shrink-0 text-success" />
          {tab}
        </span>
      </header>

      <div className="flex flex-col gap-1">
        <p className="text-body-lg font-semibold text-grey-900">{job.title}</p>
        <p className="text-body-sm text-grey-600">{formatNaira(Number(job.amount))}</p>
      </div>

      <dl className="flex flex-col gap-1 text-body-sm">
        <div className="flex gap-1.5">
          <dt className="font-medium text-grey-900">Job status</dt>
          <dd className="text-grey-900">{jobStatusLabel(job)}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="font-medium text-grey-900">Payment status</dt>
          <dd className="text-grey-900">{paymentStatusLabel(job)}</dd>
        </div>
      </dl>

      <Link href={`/worker/jobs/${job.id}`} className="self-end">
        <Button variant="outline" size="md" className="rounded-pill px-6">
          Job Details
        </Button>
      </Link>
    </article>
  );
}

export function JobsList() {
  const load = useCallback(() => getMyJobs(), []);
  const { data, error, loading } = useWorkerResource(load, "This account has no worker profile.");
  const jobs = data ?? [];
  const [tab, setTab] = useState<Tab>("All");
  const shown = tab === "All" ? jobs : jobs.filter((job) => jobTab(job) === tab);

  return (
    <main className="flex flex-col">
      <header className="border-b border-stroke px-6 pt-8 pb-5">
        <h1 className="text-body-lg font-semibold text-grey-900">Jobs</h1>
      </header>

      <div role="tablist" aria-label="Filter jobs" className="flex border-b border-stroke px-6 pt-4">
        {TABS.map((name) => {
          const selected = tab === name;
          return (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setTab(name)}
              className={cn(
                "flex-1 border-b-2 px-2 pb-3 text-body-md transition-colors",
                selected
                  ? "border-primary-500 bg-primary-50 font-medium text-grey-900"
                  : "border-transparent text-grey-400",
              )}
            >
              {name}
            </button>
          );
        })}
      </div>

      <RecordGate loading={loading} error={error}>
        <div className="flex flex-col gap-4 px-6 pt-6">
          {shown.length === 0 ? (
            <p className="text-body-sm text-grey-600">Nothing here yet.</p>
          ) : (
            shown.map((job) => <JobCard key={job.id} job={job} />)
          )}
        </div>
      </RecordGate>
    </main>
  );
}

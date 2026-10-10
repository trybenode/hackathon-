"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { CreateJobDialog } from "@/components/worker/CreateJobDialog";
import { BriefcaseIcon, LockIcon } from "@/components/worker/icons";
import { RecordGate } from "@/components/worker/RecordGate";
import { useWorkerRecord } from "@/components/worker/useWorkerRecord";
import { useWorkerResource } from "@/components/worker/useWorkerResource";
import { BellIcon, Button, CheckCircleIcon, CheckIcon, DotIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { getOnboarding } from "@/lib/onboarding";
import { getMyJobs, jobTab, type WorkerJob } from "@/lib/workerJobs";
import { formatNaira, formatShortDate, initialsOf } from "@/lib/workerFormat";

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

function GuarantorMissingIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
      <circle cx="10" cy="8" r="3.5" />
      <path d="M3.5 20a6.5 6.5 0 0 1 10.6-5" />
      <path d="M17 15.5a2 2 0 1 1 2.6 1.9c-.4.1-.6.4-.6.8v.3M19 20.5h.01" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden>
      <path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1" />
    </svg>
  );
}

/** The three money milestones on the current job card. */
function paymentProgress(job: WorkerJob): { step: number; title: string; note: string } {
  switch (job.stage) {
    case "awaiting_customer":
    case "awaiting_payment":
      return { step: 1, title: "Waiting for payment", note: "Share the job link with your customer" };
    case "awaiting_confirmation":
      return { step: 2, title: "Funds secured", note: "Waiting for the customer to release the payment" };
    case "disputed":
      return { step: 2, title: "Funds held in dispute", note: "Payscrow is reviewing the dispute" };
    case "released":
      return { step: 3, title: "Payment released", note: "The job is closed" };
    default:
      return { step: 2, title: "Funds secured", note: "Awaiting Job completion and release conditions" };
  }
}

const STATUS: Partial<Record<WorkerJob["stage"], { label: string; dot: string }>> = {
  awaiting_customer: { label: "Awaiting customer", dot: "text-grey-400" },
  awaiting_payment: { label: "Awaiting payment", dot: "text-warning" },
  held: { label: "In progress", dot: "text-info" },
  awaiting_confirmation: { label: "Completed", dot: "text-success" },
  disputed: { label: "In dispute", dot: "text-orange" },
};

/** The job most worth the worker's attention right now. */
function currentJob(jobs: WorkerJob[]) {
  const order: WorkerJob["stage"][] = ["held", "awaiting_confirmation", "disputed", "awaiting_payment", "awaiting_customer"];
  for (const stage of order) {
    const found = jobs.find((job) => job.stage === stage);
    if (found) return found;
  }
  return null;
}

function CurrentJobCard({ job }: { job: WorkerJob }) {
  const progress = paymentProgress(job);
  const status = STATUS[job.stage];

  return (
    <article className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-pill border border-stroke text-grey-800">
          <BriefcaseIcon width={20} height={20} />
        </span>
        <div className="flex flex-1 flex-col gap-1">
          <div className="flex items-start justify-between gap-2">
            <p className="text-body-md font-medium text-grey-900">{job.title}</p>
            {status && (
              <span className="flex shrink-0 items-center gap-1.5 text-body-sm text-grey-900">
                <DotIcon className={cn("shrink-0", status.dot)} />
                {status.label}
              </span>
            )}
          </div>
          <p className="text-body-sm text-grey-900">
            Customer · {job.client_name ? job.client_name.split(" ")[0] + " " + (job.client_name.split(" ")[1]?.[0] ?? "") : "not yet"}
          </p>
          <p className="text-body-md font-semibold text-grey-900">{formatNaira(Number(job.amount))}</p>
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-stroke pt-4">
        <div className="flex items-center justify-between text-body-sm text-grey-900">
          <span>Payment progress</span>
          <span>{progress.step} of 3</span>
        </div>
        <div className="flex gap-1" aria-hidden>
          {[1, 2, 3].map((segment) => (
            <span
              key={segment}
              className={cn("h-1 flex-1 rounded-pill", segment <= progress.step ? "bg-success" : "bg-grey-200")}
            />
          ))}
        </div>
        <div className="flex items-start gap-2">
          <CheckCircleIcon className="mt-0.5 shrink-0 text-success" width={18} height={18} />
          <span className="flex flex-col">
            <span className="text-body-sm text-grey-900">{progress.title}</span>
            <span className="text-xs leading-4 text-grey-900">{progress.note}</span>
          </span>
        </div>
        <Link href={`/worker/jobs/${job.id}`} className="self-end">
          <Button variant="outline" size="md" className="rounded-xl px-8">
            View job details
          </Button>
        </Link>
      </div>
    </article>
  );
}

export function WorkerHome() {
  const loadJobs = useCallback(() => getMyJobs(), []);
  const { data: jobs, error, loading, reload } = useWorkerResource(loadJobs, "This account has no worker profile.");
  const loadOnboarding = useCallback(() => getOnboarding(), []);
  const { data: onboarding } = useWorkerResource(loadOnboarding, "This account has no worker profile.");
  // Job links need an active guarantor; until we know, keep the button shut.
  const locked = onboarding?.guarantor !== "active";
  const { data: record } = useWorkerRecord();
  const [creating, setCreating] = useState(false);
  const [hello] = useState(greeting);

  const active = (jobs ?? []).filter((job) => jobTab(job) === "Active").length;
  const completed = (jobs ?? []).filter((job) => job.stage === "released").length;
  const current = currentJob(jobs ?? []);
  const guarantor = record?.credentials.guarantor ?? null;

  return (
    <main className="flex flex-col">
      <header className="flex items-start justify-between gap-3 border-b border-stroke px-6 pt-8 pb-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-body-lg font-semibold text-grey-900">
            {hello}
            {record ? `, ${record.name.split(" ")[0]}` : ""}
          </h1>
          <p className="text-body-sm text-grey-900">Manage your jobs and customer payment</p>
        </div>
        <Link href="/worker/notifications" aria-label="Notifications" className="relative mt-1 text-grey-900">
          <BellIcon width={22} height={22} />
        </Link>
      </header>

      <RecordGate loading={loading} error={error}>
        <div className="flex flex-col gap-5 px-6 pt-4 pb-6">
          <section className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 text-info">
                <LinkIcon />
              </span>
              <div className="flex flex-col gap-1">
                <h2 className="text-body-md text-grey-900">Create a job link</h2>
                <p className="text-xs leading-4 text-grey-900">Create a job agreement and send it your customer</p>
              </div>
            </div>
            <Button
              fullWidth
              variant={locked ? "ghost" : "fill"}
              className={cn("rounded-lg font-semibold", locked && "bg-grey-600/70 text-white/85 disabled:opacity-100")}
              disabled={locked}
              onClick={() => setCreating(true)}
            >
              Create Job
            </Button>
          </section>

          <section className="grid grid-cols-2 gap-3">
            {[
              { label: "Active Jobs", value: active, icon: <span className="h-6 w-6 rounded-pill bg-info" /> },
              {
                label: "Completed Jobs",
                value: completed,
                icon: (
                  <span className="flex h-6 w-6 items-center justify-center rounded-pill bg-info">
                    <CheckIcon className="text-white" width={14} height={14} />
                  </span>
                ),
              },
            ].map((stat) => (
              <div key={stat.label} className="flex flex-col gap-3 rounded-xl border border-stroke bg-white p-4">
                <span className="flex h-10 w-10 items-center justify-center rounded-pill bg-primary-50">{stat.icon}</span>
                <span className="flex flex-col gap-1">
                  {/* A worker with no jobs yet sees a dash rather than a zero. */}
                  <span className="text-body-lg text-grey-900">{jobs?.length ? stat.value : "—"}</span>
                  <span className="text-body-sm text-grey-600">{stat.label}</span>
                </span>
              </div>
            ))}
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-body-md font-semibold text-grey-900">Current job</h2>
            {current ? (
              <CurrentJobCard job={current} />
            ) : (
              <article className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4 text-center">
                <div className="flex flex-col gap-2 py-2">
                  <p className="text-body-md font-semibold text-grey-900">No current job</p>
                  <p className="text-body-sm text-grey-900">Your current Job will appear here once you have one</p>
                </div>
                {locked && (
                  <p className="flex items-center justify-center gap-2 border-t border-stroke pt-4 text-body-sm text-grey-900">
                    <LockIcon className="shrink-0" />
                    Job creation opens once your guarantor is active.
                  </p>
                )}
              </article>
            )}
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-body-md font-semibold text-grey-900">My Guarantee</h2>
            <article className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4">
              {guarantor ? (
                <>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-pill bg-primary-400 text-body-md text-white">
                        {initialsOf(guarantor.name)}
                      </span>
                      <span className="flex flex-col">
                        <span className="text-body-md text-grey-900">{guarantor.name}</span>
                        <span className="text-body-sm text-grey-600">Your Guarantor</span>
                      </span>
                    </div>
                    <span className="flex items-center gap-1.5 text-body-sm text-grey-900">
                      <DotIcon className={guarantor.status === "Active" ? "text-success" : "text-grey-800"} />
                      {guarantor.status}
                    </span>
                  </div>
                  <p className="text-body-sm text-grey-900">Valid until - {formatShortDate(guarantor.valid_until)}</p>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-pill bg-grey-200 text-grey-800">
                      <GuarantorMissingIcon />
                    </span>
                    <span className="flex flex-col">
                      <span className="text-body-md text-grey-900">No active guarantor</span>
                      <span className="text-xs leading-4 text-grey-600">Add someone who can vouch for you</span>
                    </span>
                  </div>
                  <Link href="/join/guarantor" className="self-end">
                    <Button variant="outline" size="md" className="rounded-lg px-10 font-semibold">
                      Add guarantor
                    </Button>
                  </Link>
                </>
              )}
            </article>
          </section>
        </div>
      </RecordGate>

      <CreateJobDialog open={creating} onClose={() => setCreating(false)} onCreated={() => reload()} />
    </main>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { ArrowLeftIcon, ArrowRightIcon, PinIcon, ShieldIcon } from "@/components/worker/icons";
import { RadioGroup } from "@/components/worker/RadioGroup";
import { RecordGate } from "@/components/worker/RecordGate";
import { Timeline, type TimelineStep } from "@/components/worker/Timeline";
import { useWorkerResource } from "@/components/worker/useWorkerResource";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button, CheckIcon, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";
import { ApiError } from "@/lib/guarantor";
import {
  ISSUE_REASONS,
  completeJob,
  getMyJob,
  reportIssue,
  type WorkerJob,
} from "@/lib/workerJobs";
import { formatNaira, formatShortDate, formatTime, initialsOf } from "@/lib/workerFormat";

/** The job's own progress, as opposed to the money's (see the escrow screen). */
function jobSteps(job: WorkerJob): TimelineStep[] {
  const { stage } = job;
  const started = stage !== "awaiting_payment";
  const finished = Boolean(job.completed_at) || stage === "released";
  const fundedAt = job.escrow?.funded_at ?? null;

  return [
    {
      label: "work assigned",
      at: `${formatTime(job.assigned_at)}  ${formatShortDate(job.assigned_at)}`,
      state: "done",
    },
    {
      // Work starts once the client's money is safely held.
      label: started ? "Job in progress" : "Awaiting client payment",
      at: fundedAt ? formatTime(fundedAt) : null,
      state: !started ? "current" : finished ? "done" : "current",
    },
    {
      label: "Completed",
      at: job.completed_at ? formatTime(job.completed_at) : null,
      state: finished ? "done" : "pending",
    },
    {
      label: stage === "disputed" ? "Under dispute" : "Awaiting Confirmations",
      at: job.escrow?.released_at ? formatTime(job.escrow.released_at) : null,
      state:
        stage === "released"
          ? "done"
          : stage === "awaiting_confirmation" || stage === "disputed"
            ? "current"
            : "pending",
    },
  ];
}

type Reason = (typeof ISSUE_REASONS)[number];

const COMPLAINT_LIMIT = 234;

function failure(cause: unknown, fallback: string) {
  return cause instanceof ApiError ? cause.message : fallback;
}

export function JobDetails({ jobId }: { jobId: string }) {
  const router = useRouter();
  const load = useCallback(() => getMyJob(jobId), [jobId]);
  const { data: job, error, loading } = useWorkerResource(load, "We could not find that job.");

  const [confirming, setConfirming] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [reason, setReason] = useState<Reason | null>(null);
  const [complaint, setComplaint] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // "Other" has no meaning without an explanation, so it needs the text.
  const canSubmit = reason !== null && (reason !== "Other" || complaint.trim().length > 0);

  function closeReport() {
    setReporting(false);
    setReason(null);
    setComplaint("");
    setActionError(null);
  }

  async function confirmCompletion() {
    setBusy(true);
    setActionError(null);
    try {
      await completeJob(jobId);
      setConfirming(false);
      router.push(`/worker/jobs/${jobId}/escrow`);
    } catch (cause) {
      setActionError(failure(cause, "Could not mark the job complete. Try again."));
    } finally {
      setBusy(false);
    }
  }

  async function submitIssue() {
    if (!reason) return;
    setBusy(true);
    setActionError(null);
    try {
      await reportIssue(jobId, reason, complaint.trim());
      closeReport();
      router.push(`/worker/jobs/${jobId}/escrow`);
    } catch (cause) {
      setActionError(failure(cause, "Could not report the issue. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Job Details</h1>
      </header>

      <RecordGate loading={loading} error={error}>
        {job && (
          <div className="flex flex-col gap-8 px-6 pt-8">
            <section className="flex flex-col gap-6 rounded-xl border border-stroke bg-white p-4 shadow-1">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-pill bg-primary-400 text-body-md font-medium text-white">
                  {initialsOf(job.client_name ?? "Client")}
                </span>
                <span className="flex flex-col">
                  <span className="text-body-md text-grey-900">{job.client_name ?? "Client"}</span>
                  <span className="text-body-sm text-grey-600">Client</span>
                </span>
              </div>

              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <p className="text-body-md font-medium text-grey-900">{job.title}</p>
                  <p className="text-body-sm text-grey-600">{formatNaira(Number(job.amount))}</p>
                </div>
                {job.location && (
                  <span className="flex items-center gap-1 text-body-sm text-grey-600">
                    <PinIcon className="shrink-0" />
                    {job.location}
                  </span>
                )}
              </div>

              {job.details.length > 0 && (
                <dl className="grid grid-cols-2 gap-x-6 gap-y-4 pt-4">
                  {job.details.map((detail) => (
                    <div key={detail.label} className="flex flex-col gap-0.5">
                      <dt className="text-body-sm text-grey-900">{detail.label}</dt>
                      <dd className="text-body-sm text-grey-600">{detail.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>

            <Timeline steps={jobSteps(job)} />

            <section className="flex flex-col gap-2 rounded-lg bg-primary-25 p-4">
              <h2 className="flex items-center gap-2 text-body-md font-medium text-grey-900">
                <ShieldIcon className="text-info" />
                Payment Protected
              </h2>
              <p className="pl-7 text-body-md font-semibold text-grey-900">
                {formatNaira(Number(job.amount))}
              </p>
              <p className="pl-7 text-xs leading-4 text-grey-900">
                {job.stage === "awaiting_payment"
                  ? "Waiting for the client to pay into escrow"
                  : "Held securely until job is confirmed"}
              </p>
              <Link
                href={`/worker/jobs/${job.id}/escrow`}
                className="mt-1 flex items-center gap-2 self-end text-body-sm text-info"
              >
                view escrow details
                <ArrowRightIcon />
              </Link>
            </section>

            {job.stage === "held" && (
              <div className="flex flex-col items-center gap-3 pb-4">
                <Button size="lg" className="w-56 rounded-lg" onClick={() => setConfirming(true)}>
                  Mark as complete
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  className="w-56 rounded-lg"
                  onClick={() => setReporting(true)}
                >
                  Report an issue
                </Button>
              </div>
            )}
          </div>
        )}
      </RecordGate>

      <WorkerDialog open={confirming} onClose={() => setConfirming(false)} label="Confirm Completion">
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-pill bg-primary-400">
            <CheckIcon className="text-white" width={28} height={28} />
          </span>
          <h2 className="text-h3 text-grey-900">Confirm Completion</h2>
          <p className="text-body-md text-grey-900">Confirm that you have completed this job</p>
          {actionError && confirming && (
            <p role="alert" className="text-body-sm text-error">
              {actionError}
            </p>
          )}
          <div className="mt-2 flex w-full gap-4">
            <Button variant="outline" fullWidth className="rounded-lg" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button fullWidth className="rounded-lg" disabled={busy} onClick={confirmCompletion}>
              {busy ? "Confirming…" : "Confirm"}
            </Button>
          </div>
        </div>
      </WorkerDialog>

      <WorkerDialog open={reporting} onClose={closeReport} label="Report an issue">
        <div className="flex flex-col gap-5">
          <h2 className="text-body-lg font-semibold text-grey-900">Report an issue</h2>
          <p className="text-body-lg text-grey-900">What&rsquo;s the issue?</p>

          <RadioGroup
            legend="What's the issue?"
            options={ISSUE_REASONS}
            value={reason}
            onChange={setReason}
          />

          <Textarea
            label="Enter Your Complaint"
            placeholder="Input text"
            rows={5}
            maxLength={COMPLAINT_LIMIT}
            showCount
            value={complaint}
            onChange={(event) => setComplaint(event.target.value)}
          />

          {actionError && reporting && (
            <p role="alert" className="text-body-sm text-error">
              {actionError}
            </p>
          )}

          <div className="flex gap-4">
            <Button variant="outline" fullWidth className="rounded-lg" onClick={closeReport}>
              Cancel
            </Button>
            <Button
              fullWidth
              disabled={!canSubmit || busy}
              className={cn("rounded-lg", !canSubmit && "opacity-50")}
              onClick={submitIssue}
            >
              {busy ? "Submitting…" : "Submit"}
            </Button>
          </div>
        </div>
      </WorkerDialog>
    </main>
  );
}

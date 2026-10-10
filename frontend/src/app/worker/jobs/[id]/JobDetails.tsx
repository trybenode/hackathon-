"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { DisputeDialog } from "@/components/jobs/DisputeDialog";
import { jobProgress } from "@/components/jobs/jobProgress";
import { ReportIssueDialog } from "@/components/jobs/ReportIssueDialog";
import { ArrowLeftIcon, ShieldIcon } from "@/components/worker/icons";
import { CopyLinkButton } from "@/components/worker/CopyLinkButton";
import { RecordGate } from "@/components/worker/RecordGate";
import { Timeline } from "@/components/worker/Timeline";
import { useWorkerResource } from "@/components/worker/useWorkerResource";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button, CalendarIcon, CheckIcon, ClockIcon, LocationPinIcon } from "@/components/ui";
import { ApiError } from "@/lib/guarantor";
import { WORKER_ISSUE_REASONS, completeJob, getMyJob, reportIssue } from "@/lib/workerJobs";
import { formatClock, formatDayMonth, formatNaira, initialsOf } from "@/lib/workerFormat";

export function JobDetails({ jobId }: { jobId: string }) {
  const router = useRouter();
  const load = useCallback(() => getMyJob(jobId), [jobId]);
  const { data: job, error, loading, reload } = useWorkerResource(load, "We could not find that job.");

  const [confirming, setConfirming] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [viewingDispute, setViewingDispute] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function confirmCompletion() {
    setBusy(true);
    setActionError(null);
    try {
      await completeJob(jobId);
      setConfirming(false);
      reload();
    } catch (cause) {
      setActionError(cause instanceof ApiError ? cause.message : "Could not mark the job complete.");
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
          <div className="flex flex-col gap-6 px-6 pt-8">
            <section className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4 shadow-1">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-pill bg-primary-500 text-body-md font-medium text-white">
                  {job.client_name ? initialsOf(job.client_name) : "?"}
                </span>
                <span className="flex flex-col">
                  <span className="text-body-md text-grey-900">
                    {job.client_name ?? "Waiting for your customer"}
                  </span>
                  <span className="text-xs leading-4 text-grey-600">Client</span>
                </span>
              </div>
              <p className="text-body-sm font-medium text-grey-900">{job.title}</p>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs leading-4 text-grey-900">
                {job.address && (
                  <span className="flex items-center gap-1.5">
                    <LocationPinIcon className="shrink-0" width={14} height={14} />
                    {job.address}
                  </span>
                )}
                {job.scheduled_at && (
                  <>
                    <span className="flex items-center gap-1.5">
                      <ClockIcon className="shrink-0" width={14} height={14} />
                      {formatClock(job.scheduled_at)}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <CalendarIcon className="shrink-0" width={14} height={14} />
                      {formatDayMonth(job.scheduled_at)}
                    </span>
                  </>
                )}
              </div>
              {job.stage === "awaiting_customer" && (
                <div className="flex flex-col gap-2 border-t border-stroke pt-4">
                  <p className="text-body-sm text-grey-900">
                    Send your customer this link. Their details appear here once they pay.
                  </p>
                  <CopyLinkButton link={job.link} />
                </div>
              )}
            </section>

            <section className="flex flex-col gap-4">
              <h2 className="text-body-md font-semibold text-grey-900">Job Progress</h2>
              <Timeline steps={jobProgress(job, "worker")} />
            </section>

            <section className="flex flex-col gap-2 rounded-lg bg-primary-25 p-4">
              <h2 className="flex items-center gap-2 text-body-md font-medium text-grey-900">
                <ShieldIcon className="text-info" />
                Payment Protected
              </h2>
              <p className="pl-7 text-body-md font-semibold text-grey-900">{formatNaira(Number(job.amount))}</p>
              <p className="pl-7 text-xs leading-4 text-grey-900">
                {job.stage === "awaiting_customer" || job.stage === "awaiting_payment"
                  ? "Held securely in escrow once your customer pays"
                  : job.stage === "released"
                    ? "Released to you"
                    : "Held securely until job is confirmed"}
              </p>
            </section>

            {job.stage === "held" && (
              <div className="flex flex-col items-center gap-3 pb-4">
                <Button size="lg" className="w-56 rounded-xl px-0 text-body-lg font-semibold" onClick={() => setConfirming(true)}>
                  Mark as complete
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  className="w-56 rounded-xl px-0 text-body-lg font-semibold"
                  onClick={() => setReporting(true)}
                >
                  Report an issue
                </Button>
              </div>
            )}

            {job.dispute && (
              <div className="flex flex-col items-center pb-4">
                <Button
                  size="lg"
                  variant="outline"
                  className="w-56 rounded-xl px-0 text-body-lg font-semibold"
                  onClick={() => setViewingDispute(true)}
                >
                  View dispute
                </Button>
              </div>
            )}

            {job.dispute && (
              <DisputeDialog dispute={job.dispute} open={viewingDispute} onClose={() => setViewingDispute(false)} />
            )}
          </div>
        )}
      </RecordGate>

      <WorkerDialog open={confirming} onClose={() => setConfirming(false)} label="Confirm Completion">
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-pill bg-primary-500">
            <CheckIcon className="text-white" width={28} height={28} />
          </span>
          <h2 className="text-body-lg font-semibold text-grey-900">Confirm Completion</h2>
          <p className="text-body-md text-grey-900">Confirm that you have completed this job</p>
          {actionError && (
            <p role="alert" className="text-body-sm text-error">
              {actionError}
            </p>
          )}
          <div className="mt-2 flex w-full gap-4">
            <Button variant="outline" size="lg" fullWidth className="min-w-0 rounded-xl px-0" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button size="lg" fullWidth className="min-w-0 rounded-xl px-0" disabled={busy} onClick={confirmCompletion}>
              {busy ? "Confirming…" : "Confirm"}
            </Button>
          </div>
        </div>
      </WorkerDialog>

      <ReportIssueDialog
        open={reporting}
        onClose={() => setReporting(false)}
        reasons={WORKER_ISSUE_REASONS}
        onSubmit={async (reason, complaint, evidence) => {
          await reportIssue(jobId, reason, complaint, evidence);
          reload();
        }}
      />
    </main>
  );
}

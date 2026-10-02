"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeftIcon, ArrowRightIcon, PinIcon, ShieldIcon } from "@/components/worker/icons";
import { useJobs } from "@/components/worker/JobsProvider";
import { RadioGroup } from "@/components/worker/RadioGroup";
import { Timeline, type TimelineStep } from "@/components/worker/Timeline";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button, CheckIcon, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";
import {
  ISSUE_REASONS,
  formatNaira,
  formatShortDate,
  formatTime,
  initialsOf,
  type WorkerJob,
} from "@/lib/workerMock";

/** The job's own progress, as opposed to the money's (see the escrow screen). */
function jobSteps(job: WorkerJob): TimelineStep[] {
  const stage = job.escrowStage;
  const finished = stage !== "held";

  return [
    {
      label: "work assigned",
      at: `${formatTime(job.assignedAt)}  ${formatShortDate(job.assignedAt)}`,
      state: "done",
    },
    {
      label: "Job in progress",
      at: formatTime(job.startedAt),
      state: finished ? "done" : "current",
    },
    {
      label: "Completed",
      at: job.completedAt ? formatTime(job.completedAt) : null,
      state: finished ? "done" : "pending",
    },
    {
      label: stage === "disputed" ? "Under dispute" : "Awaiting Confirmations",
      at: job.confirmedAt ? formatTime(job.confirmedAt) : null,
      state: stage === "released" ? "done" : finished ? "current" : "pending",
    },
  ];
}

type Reason = (typeof ISSUE_REASONS)[number];

const COMPLAINT_LIMIT = 234;

export function JobDetails({ jobId }: { jobId: string }) {
  const router = useRouter();
  const { getJob, markComplete, reportIssue } = useJobs();
  const job = getJob(jobId);

  const [confirming, setConfirming] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [reason, setReason] = useState<Reason | null>(null);
  const [complaint, setComplaint] = useState("");

  if (!job) {
    return (
      <main className="px-6 pt-10">
        <p className="text-body-sm text-grey-600">We could not find that job.</p>
      </main>
    );
  }

  const inProgress = job.escrowStage === "held";
  // "Other" has no meaning without an explanation, so it needs the text.
  const canSubmit = reason !== null && (reason !== "Other" || complaint.trim().length > 0);

  function closeReport() {
    setReporting(false);
    setReason(null);
    setComplaint("");
  }

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Job Details</h1>
      </header>

      <div className="flex flex-col gap-8 px-6 pt-8">
        <section className="flex flex-col gap-6 rounded-xl border border-stroke bg-white p-4 shadow-1">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-pill bg-primary-400 text-body-md font-medium text-white">
              {initialsOf(job.clientName)}
            </span>
            <span className="flex flex-col">
              <span className="text-body-md text-grey-900">{job.clientName}</span>
              <span className="text-body-sm text-grey-600">Client</span>
            </span>
          </div>

          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <p className="text-body-md font-medium text-grey-900">{job.title}</p>
              <p className="text-body-sm text-grey-600">{formatNaira(job.amount)}</p>
            </div>
            <span className="flex items-center gap-1 text-body-sm text-grey-600">
              <PinIcon className="shrink-0" />
              {job.location}
            </span>
          </div>

          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 pt-4">
            {job.details.map((detail) => (
              <div key={detail.label} className="flex flex-col gap-0.5">
                <dt className="text-body-sm text-grey-900">{detail.label}</dt>
                <dd className="text-body-sm text-grey-600">{detail.value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <Timeline steps={jobSteps(job)} />

        <section className="flex flex-col gap-2 rounded-lg bg-primary-25 p-4">
          <h2 className="flex items-center gap-2 text-body-md font-medium text-grey-900">
            <ShieldIcon className="text-info" />
            Payment Protected
          </h2>
          <p className="pl-7 text-body-md font-semibold text-grey-900">{formatNaira(job.amount)}</p>
          <p className="pl-7 text-xs leading-4 text-grey-900">Held securely until job is confirmed</p>
          <Link
            href={`/worker/jobs/${job.id}/escrow`}
            className="mt-1 flex items-center gap-2 self-end text-body-sm text-info"
          >
            view escrow details
            <ArrowRightIcon />
          </Link>
        </section>

        {inProgress && (
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

      <WorkerDialog open={confirming} onClose={() => setConfirming(false)} label="Confirm Completion">
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-pill bg-primary-400">
            <CheckIcon className="text-white" width={28} height={28} />
          </span>
          <h2 className="text-h3 text-grey-900">Confirm Completion</h2>
          <p className="text-body-md text-grey-900">Confirm that you have completed this job</p>
          <div className="mt-2 flex w-full gap-4">
            <Button variant="outline" fullWidth className="rounded-lg" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button
              fullWidth
              className="rounded-lg"
              onClick={() => {
                markComplete(job.id);
                setConfirming(false);
                router.push(`/worker/jobs/${job.id}/escrow`);
              }}
            >
              Confirm
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

          <div className="flex gap-4">
            <Button variant="outline" fullWidth className="rounded-lg" onClick={closeReport}>
              Cancel
            </Button>
            <Button
              fullWidth
              disabled={!canSubmit}
              className={cn("rounded-lg", !canSubmit && "opacity-50")}
              onClick={() => {
                if (!reason) return;
                reportIssue(job.id, reason, complaint.trim());
                closeReport();
                router.push(`/worker/jobs/${job.id}/escrow`);
              }}
            >
              Submit
            </Button>
          </div>
        </div>
      </WorkerDialog>
    </main>
  );
}

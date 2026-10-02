"use client";

import { useRouter } from "next/navigation";
import { ArrowLeftIcon, CoverageIcon, LockIcon, ShieldIcon } from "@/components/worker/icons";
import { useJobs } from "@/components/worker/JobsProvider";
import { Timeline, type TimelineStep } from "@/components/worker/Timeline";
import { DotIcon } from "@/components/ui";
import {
  formatLongDate,
  formatNaira,
  formatShortDate,
  formatTime,
  type WorkerJob,
} from "@/lib/workerMock";

/** The money's progress: received, held, then released or disputed. */
function escrowSteps(job: WorkerJob): TimelineStep[] {
  const stage = job.escrowStage;
  const workDone = stage !== "held";

  const opening: TimelineStep[] = [
    {
      label: "Payment received",
      at: `${formatTime(job.paymentReceivedAt)}  ${formatShortDate(job.paymentReceivedAt)}`,
      state: "done",
    },
    { label: "Funds held", at: formatTime(job.fundsHeldAt), state: "done" },
    {
      label: "Job completed",
      at: job.completedAt ? formatTime(job.completedAt) : null,
      state: workDone ? "done" : "pending",
    },
  ];

  // A dispute replaces the confirm-and-release ending with a review.
  if (stage === "disputed") {
    return [
      ...opening,
      { label: "Dispute under review", state: "current" },
      { label: "Resolution", state: "pending" },
    ];
  }

  return [
    ...opening,
    {
      label: "Clients confirmation",
      at: job.confirmedAt ? formatTime(job.confirmedAt) : null,
      state: stage === "released" ? "done" : stage === "awaiting_confirmation" ? "current" : "pending",
    },
    {
      label: "Funds released",
      at: job.releasedAt ? formatTime(job.releasedAt) : null,
      state: stage === "released" ? "done" : "pending",
    },
  ];
}

const SUBTITLE: Record<WorkerJob["escrowStage"], string> = {
  held: "Held securely",
  awaiting_confirmation: "Held securely",
  disputed: "Payment under dispute",
  // The released frame still reads "Held securely", which is no longer true
  // once the money has gone out; flagged with the designer.
  released: "Released",
};

function Protection({ job }: { job: WorkerJob }) {
  return (
    <section className="flex flex-col gap-4 rounded-lg bg-primary-25 p-4">
      <div className="flex flex-col gap-1">
        <h2 className="flex items-center gap-2 text-body-md font-medium text-grey-900">
          <ShieldIcon className="text-info" />
          Payment &amp; Protection
        </h2>
        <p className="pl-7 text-body-md font-semibold text-grey-900">{formatNaira(job.amount)}</p>
        <p className="pl-7 text-body-sm text-grey-900">Protected</p>
        <p className="pl-7 text-xs leading-4 text-grey-900">Until Job Confirmation</p>
      </div>

      <div className="flex flex-col gap-1 rounded-lg border border-primary-100 bg-white p-3">
        <p className="flex items-center gap-2 text-body-sm text-info">
          <LockIcon />
          Guarantee
        </p>
        <div className="flex items-center justify-between gap-2 text-body-sm">
          <span className="font-semibold text-grey-900">Escrow-backed</span>
          <span className="text-grey-900">{job.escrowReference.replace("ESC-", "ESC -")}</span>
        </div>
        <p className="text-body-sm text-grey-900">Payment held until confirmation</p>
      </div>

      <div className="flex flex-col gap-1 rounded-lg border border-primary-100 bg-white p-3">
        <p className="flex items-center gap-2 text-body-sm text-info">
          <CoverageIcon />
          Coverage
          <span className="flex items-center gap-1 text-grey-900">
            <DotIcon className={job.coverageActive ? "text-success" : "text-grey-400"} />
            {job.coverageActive ? "Active" : "Inactive"}
          </span>
        </p>
        <p className="text-body-sm text-grey-900">
          {/* FR-6.3: cover only runs once the micro-premium is paid. */}
          {job.coverageActive ? "Micro- insurance is active" : "Micro-insurance is not active"}
        </p>
      </div>
    </section>
  );
}

function Summary({ job }: { job: WorkerJob }) {
  if (job.escrowStage === "disputed" && job.dispute) {
    return (
      <dl className="flex flex-col gap-2 text-body-sm">
        <div className="flex gap-1.5">
          <dt className="text-grey-900">Dispute</dt>
          <dd className="text-grey-900">#{job.dispute.id}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-grey-900">Submitted</dt>
          <dd className="text-grey-900">{formatLongDate(job.dispute.submittedAt).toLowerCase()}</dd>
        </div>
      </dl>
    );
  }

  const settled = job.escrowStage === "released";
  const when = settled ? job.releasedAt : job.completedAt;

  return (
    <dl className="flex flex-col gap-2 text-body-sm">
      <dt className="text-grey-900">{settled ? "Released" : "Job completed"}</dt>
      <dd className="text-grey-900">{when ? formatLongDate(when) : "—"}</dd>
    </dl>
  );
}

export function EscrowStatus({ jobId }: { jobId: string }) {
  const router = useRouter();
  const { getJob } = useJobs();
  const job = getJob(jobId);

  if (!job) {
    return (
      <main className="px-6 pt-10">
        <p className="text-body-sm text-grey-600">We could not find that job.</p>
      </main>
    );
  }

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Escrow</h1>
      </header>

      <div className="flex flex-col gap-8 px-6 pt-8">
        <div className="flex flex-col gap-1">
          <p className="text-body-lg font-semibold text-grey-900">{formatNaira(job.amount)}</p>
          <p className="text-body-sm text-grey-900">{SUBTITLE[job.escrowStage]}</p>
        </div>

        <Timeline steps={escrowSteps(job)} />

        {job.escrowStage === "held" ? <Protection job={job} /> : <Summary job={job} />}
      </div>
    </main>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { ArrowLeftIcon, CoverageIcon, LockIcon, ShieldIcon } from "@/components/worker/icons";
import { RecordGate } from "@/components/worker/RecordGate";
import { Timeline, type TimelineStep } from "@/components/worker/Timeline";
import { useWorkerResource } from "@/components/worker/useWorkerResource";
import { DotIcon } from "@/components/ui";
import { getMyJob, type JobStage, type WorkerJob } from "@/lib/workerJobs";
import { formatLongDate, formatNaira, formatShortDate, formatTime } from "@/lib/workerFormat";

/** The money's progress: received, held, then released, refunded or disputed. */
function escrowSteps(job: WorkerJob): TimelineStep[] {
  const { stage, escrow } = job;
  const funded = escrow?.funded_at ?? null;
  const workDone = Boolean(job.completed_at);

  const opening: TimelineStep[] = [
    {
      label: "Payment received",
      at: funded ? `${formatTime(funded)}  ${formatShortDate(funded)}` : null,
      state: funded ? "done" : "current",
    },
    { label: "Funds held", at: funded ? formatTime(funded) : null, state: funded ? "done" : "pending" },
    {
      label: "Job completed",
      at: job.completed_at ? formatTime(job.completed_at) : null,
      state: workDone ? "done" : "pending",
    },
  ];

  // A dispute replaces the confirm-and-release ending with a review.
  if (stage === "disputed" || stage === "refunded" || escrow?.resolution_type) {
    const ruled = stage === "refunded" || stage === "released";
    return [
      ...opening,
      { label: "Dispute under review", state: ruled ? "done" : "current" },
      {
        label: stage === "refunded" ? "Refunded to client" : "Resolution",
        at: escrow?.released_at ? formatTime(escrow.released_at) : null,
        state: ruled ? "done" : "pending",
      },
    ];
  }

  return [
    ...opening,
    {
      label: "Clients confirmation",
      at: escrow?.released_at ? formatTime(escrow.released_at) : null,
      state: stage === "released" ? "done" : stage === "awaiting_confirmation" ? "current" : "pending",
    },
    {
      label: "Funds released",
      at: escrow?.released_at ? formatTime(escrow.released_at) : null,
      state: stage === "released" ? "done" : "pending",
    },
  ];
}

const SUBTITLE: Record<JobStage, string> = {
  awaiting_payment: "Awaiting client payment",
  held: "Held securely",
  awaiting_confirmation: "Held securely",
  disputed: "Payment under dispute",
  // The released frame still reads "Held securely", which is no longer true
  // once the money has gone out; flagged with the designer.
  released: "Released",
  refunded: "Refunded to client",
};

function Protection({ job }: { job: WorkerJob }) {
  const reference = job.escrow?.transaction_number ?? "—";
  const covered = job.escrow?.cover_active ?? false;

  return (
    <section className="flex flex-col gap-4 rounded-lg bg-primary-25 p-4">
      <div className="flex flex-col gap-1">
        <h2 className="flex items-center gap-2 text-body-md font-medium text-grey-900">
          <ShieldIcon className="text-info" />
          Payment &amp; Protection
        </h2>
        <p className="pl-7 text-body-md font-semibold text-grey-900">
          {formatNaira(Number(job.amount))}
        </p>
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
          <span className="text-grey-900">{reference}</span>
        </div>
        <p className="text-body-sm text-grey-900">Payment held until confirmation</p>
      </div>

      <div className="flex flex-col gap-1 rounded-lg border border-primary-100 bg-white p-3">
        <p className="flex items-center gap-2 text-body-sm text-info">
          <CoverageIcon />
          Coverage
          <span className="flex items-center gap-1 text-grey-900">
            <DotIcon className={covered ? "text-success" : "text-grey-400"} />
            {covered ? "Active" : "Inactive"}
          </span>
        </p>
        <p className="text-body-sm text-grey-900">
          {/* FR-6.3: cover only runs once the micro-premium is paid. */}
          {covered ? "Micro- insurance is active" : "Micro-insurance is not active"}
        </p>
      </div>
    </section>
  );
}

function Summary({ job }: { job: WorkerJob }) {
  if (job.stage === "disputed" && job.dispute) {
    return (
      <dl className="flex flex-col gap-2 text-body-sm">
        <div className="flex gap-1.5">
          <dt className="text-grey-900">Dispute</dt>
          <dd className="text-grey-900">#{job.dispute.reference}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-grey-900">Submitted</dt>
          <dd className="text-grey-900">{formatLongDate(job.dispute.submitted_at).toLowerCase()}</dd>
        </div>
      </dl>
    );
  }

  if (job.stage === "awaiting_payment") {
    return (
      <p className="text-body-sm text-grey-900">
        The client has been sent a secure Payscrow link. Work starts once their payment is held.
      </p>
    );
  }

  const settled = job.stage === "released" || job.stage === "refunded";
  const when = settled ? job.escrow?.released_at : job.completed_at;

  return (
    <dl className="flex flex-col gap-2 text-body-sm">
      <dt className="text-grey-900">
        {job.stage === "refunded" ? "Refunded" : settled ? "Released" : "Job completed"}
      </dt>
      <dd className="text-grey-900">{when ? formatLongDate(when) : "—"}</dd>
    </dl>
  );
}

export function EscrowStatus({ jobId }: { jobId: string }) {
  const router = useRouter();
  const load = useCallback(() => getMyJob(jobId), [jobId]);
  const { data: job, error, loading } = useWorkerResource(load, "We could not find that job.");

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Escrow</h1>
      </header>

      <RecordGate loading={loading} error={error}>
        {job && (
          <div className="flex flex-col gap-8 px-6 pt-8">
            <div className="flex flex-col gap-1">
              <p className="text-body-lg font-semibold text-grey-900">
                {formatNaira(Number(job.amount))}
              </p>
              <p className="text-body-sm text-grey-900">{SUBTITLE[job.stage]}</p>
            </div>

            <Timeline steps={escrowSteps(job)} />

            {job.stage === "held" ? <Protection job={job} /> : <Summary job={job} />}
          </div>
        )}
      </RecordGate>
    </main>
  );
}

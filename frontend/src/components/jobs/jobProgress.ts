import type { TimelineStep } from "@/components/worker/Timeline";
import { formatTime } from "@/lib/workerFormat";
import type { JobStage } from "@/lib/workerJobs";

type Progress = {
  stage: JobStage;
  created_at: string;
  funded_at: string | null;
  completed_at: string | null;
  released_at: string | null;
};

/**
 * The "Job Progress" trail both the worker and the customer see (job flow
 * document, "Status trail"). Only the hint under the current step differs:
 * it tells each side what, if anything, is theirs to do.
 */
export function jobProgress(
  job: Progress,
  audience: "worker" | "customer",
  workerName = "The worker",
): TimelineStep[] {
  const at = (value: string | null) => (value ? formatTime(value) : null);
  const paid = Boolean(job.funded_at);
  const completed = Boolean(job.completed_at);
  const released = job.stage === "released";
  const firstName = workerName.split(" ")[0];

  const steps: TimelineStep[] = [
    {
      label: "Job created",
      at: `${formatTime(job.created_at)}`,
      state: "done",
    },
    {
      label: "Payment held in escrow",
      at: paid
        ? at(job.funded_at)
        : audience === "worker"
          ? "Waiting for the customer to pay"
          : "Pay to book the job",
      state: paid ? "done" : "current",
    },
  ];

  // Once the work is done, "in progress" has served its purpose.
  if (!completed) {
    steps.push({
      label: "Job in progress",
      at: paid
        ? audience === "worker"
          ? "Mark job complete once done"
          : `${firstName} is working on your job. Nothing is needed from you yet`
        : null,
      state: paid && !completed ? "current" : "pending",
    });
  }

  steps.push({ label: "Completed", at: at(job.completed_at), state: completed ? "done" : "pending" });

  if (job.stage === "disputed" || job.stage === "refunded") {
    steps.push({
      label: job.stage === "refunded" ? "Refunded to customer" : "In dispute",
      at: job.stage === "disputed" ? "Payment held while Payscrow reviews it" : null,
      state: job.stage === "refunded" ? "done" : "current",
    });
    return steps;
  }

  steps.push({
    label: "Awaiting confirmation",
    at: released
      ? at(job.released_at)
      : completed
        ? audience === "worker"
          ? "Waiting for the customer's code"
          : "Enter code to confirm work is done"
        : null,
    state: released ? "done" : completed ? "current" : "pending",
  });
  steps.push({ label: "Payment released", at: at(job.released_at), state: released ? "done" : "pending" });
  return steps;
}

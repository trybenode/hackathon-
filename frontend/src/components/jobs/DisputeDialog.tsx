"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";

import { Timeline, type TimelineStep } from "@/components/worker/Timeline";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button } from "@/components/ui";
import { formatTime } from "@/lib/workerFormat";
import type { DisputeInfo } from "@/lib/workerJobs";

/** Payscrow's stages, in order, as the frame names them. */
const STAGES: { key: string; label: string }[] = [
  { key: "NegotiationOpen", label: "Negotiation" },
  { key: "EvidenceCollection", label: "Evidence" },
  { key: "AwaitingArbiterDecision", label: "Awaiting decision" },
  { key: "Resolved", label: "Resolved" },
];

const RAISED_BY: Record<string, string> = {
  customer: "Client",
  worker: "Worker",
  timeout: "Platform",
};

const RESOLUTION: Record<string, string> = {
  Refund: "Refunded to the customer",
  Close: "Paid to the worker",
  Split: "Split between both",
};

function disputeSteps(dispute: DisputeInfo): TimelineStep[] {
  const current = Math.max(0, STAGES.findIndex((stage) => stage.key === (dispute.stage ?? "NegotiationOpen")));
  const when = new Map(dispute.history.map((step) => [step.stage, step.at]));

  return STAGES.map((stage, index) => {
    const at = when.get(stage.key);
    const resolved = stage.key === "Resolved" && dispute.resolution;
    return {
      label: stage.label,
      at: resolved ? RESOLUTION[dispute.resolution!] ?? dispute.resolution : at ? formatTime(at) : null,
      state: index < current || (index === current && stage.key === "Resolved") ? "done" : index === current ? "current" : "pending",
    };
  });
}

/** Who raised the dispute and where Payscrow's review stands; both sides see it. */
export function DisputeDialog({
  dispute,
  open,
  onClose,
}: {
  dispute: DisputeInfo;
  open: boolean;
  onClose: () => void;
}) {
  const { w } = useWorkerCopy(true);

  return (
    <WorkerDialog open={open} onClose={onClose} label={w("Dispute")}>
      <div className="flex flex-col gap-5">
        <h2 className="text-body-md font-semibold text-grey-900">{w("Dispute")}</h2>

        <dl className="flex flex-col rounded-lg border border-stroke">
          <div className="flex items-center justify-between gap-3 border-b border-stroke px-3 py-4">
            <dt className="text-body-sm text-grey-600">{w("Dispute raised")}</dt>
            <dd className="text-right text-body-sm text-grey-900">{dispute.reason}</dd>
          </div>
          <div className="flex items-center justify-between gap-3 px-3 py-4">
            <dt className="text-body-sm text-grey-600">{w("Record by")}</dt>
            <dd className="text-body-sm text-grey-900">{RAISED_BY[dispute.raised_by] ?? dispute.raised_by}</dd>
          </div>
        </dl>

        <h3 className="text-body-md font-semibold text-grey-900">{w("Dispute Progress")}</h3>
        <Timeline steps={disputeSteps(dispute)} />

        <Button variant="outline" size="lg" className="w-[calc(50%-0.5rem)] rounded-xl px-0" onClick={onClose}>
          {w("Cancel")}</Button>
      </div>
    </WorkerDialog>
  );
}

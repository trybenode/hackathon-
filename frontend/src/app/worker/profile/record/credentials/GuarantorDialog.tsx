"use client";

import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button, DotIcon, VerificationBadge } from "@/components/ui";
import { cn } from "@/lib/cn";
import { formatFullDate, initialsOf } from "@/lib/workerFormat";
import type { GuarantorCredential } from "@/lib/workerRecord";

/** The stored agreement lifecycle and supporting verification evidence. */
export function GuarantorDialog({
  guarantor,
  open,
  onClose,
}: {
  guarantor: GuarantorCredential;
  open: boolean;
  onClose: () => void;
}) {

  return (
    <WorkerDialog open={open} onClose={onClose} label="Guarantor">
      <div className="flex flex-col gap-5">
        <h2 className="text-body-md font-semibold text-grey-900">Guarantor</h2>

        <section className="flex flex-col gap-4 rounded-lg border border-stroke p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-pill bg-badge-pending-text text-body-sm text-white">
                {initialsOf(guarantor.name)}
              </span>
              <span className="flex flex-col">
                <span className="text-body-md text-grey-900">{guarantor.name}</span>
                <span className="text-xs leading-4 text-grey-600">Guarantor</span>
              </span>
            </div>
            {guarantor.verified && <VerificationBadge status="verified" className="py-1 text-xs" />}
          </div>

          <p className="flex items-center gap-2 text-body-sm text-grey-900">
            Guarantee
            <span className="flex items-center gap-1.5">
              <DotIcon className={cn("shrink-0", guarantor.status === "Active" ? "text-success" : "text-grey-800")} />
              {guarantor.status}
            </span>
          </p>
          {guarantor.sandbox && <p className="text-body-sm text-grey-600">Sandbox verification evidence</p>}
        </section>

        <section className="flex flex-col px-1">
          <h3 className="pb-2 text-body-md text-grey-900">Guarantee Information</h3>
          <dl className="flex flex-col">
            {[
              ["Relationship", guarantor.relationship ? guarantor.relationship[0].toUpperCase() + guarantor.relationship.slice(1) : "—"],
              ["Guarantee started", formatFullDate(guarantor.activated_at)],
              ["Valid until", formatFullDate(guarantor.valid_until)],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-3 border-b border-stroke py-4">
                <dt className="text-body-sm whitespace-nowrap text-grey-600">{label}</dt>
                <dd className="text-body-sm font-medium whitespace-nowrap text-grey-900">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <Button variant="outline" size="lg" onClick={onClose}>Close</Button>
      </div>
    </WorkerDialog>
  );
}

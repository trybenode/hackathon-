import Link from "next/link";
import { Button, DotIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { formatStartedOn } from "@/lib/format";
import type { GuaranteeCard as Guarantee } from "@/lib/guarantor";
import { WorkerAvatar } from "./WorkerAvatar";

/**
 * Each outcome gets its own colour so a claim that was paid out does not read
 * the same as one that was dismissed.
 */
export const statusDot: Record<string, string> = {
  Active: "text-success",
  "Pending Signature": "text-warning",
  "Pending Verification": "text-warning",
  // A claim is running: red while open, orange while contested.
  Triggered: "text-error-mid",
  Disputed: "text-orange",
  // Resolved claims: paid cost the guarantor money, dismissed did not.
  Paid: "text-grey-800",
  Dismissed: "text-success",
  Declined: "text-error-mid",
  Revoked: "text-error-mid",
  Expired: "text-grey-800",
};

/** The line under the worker: when the guarantee runs out, or when it ended. */
function termLine(guarantee: Guarantee) {
  switch (guarantee.bucket) {
    case "active":
      return `Valid until - ${formatStartedOn(guarantee.valid_until)}`;
    case "expired":
      return `Expired - ${formatStartedOn(guarantee.ended_on ?? guarantee.valid_until)}`;
    case "closed":
      return `${guarantee.status} - ${formatStartedOn(guarantee.ended_on)}`;
    case "request":
      return "Awaiting your response";
  }
}

export function GuaranteeCard({
  guarantee,
  variant = "list",
}: {
  guarantee: Guarantee;
  /** `home` says when the guarantee started; `list` says when it ends. */
  variant?: "home" | "list";
}) {
  const term =
    variant === "home"
      ? `Started - ${formatStartedOn(guarantee.started_on)}`
      : termLine(guarantee);

  return (
    <article className="flex flex-col gap-10 rounded-xl border border-stroke bg-white p-4 shadow-1">
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <WorkerAvatar name={guarantee.worker_name} src={guarantee.avatar_url} />
          <span className="flex flex-col">
            <span className="text-body-md font-medium text-grey-900">
              {guarantee.worker_name}
            </span>
            <span className="text-body-sm text-grey-600">{guarantee.worker_role ?? ""}</span>
          </span>
        </div>

        <span className="flex items-center gap-1.5 text-body-sm text-grey-900">
          <DotIcon className={cn("shrink-0", statusDot[guarantee.status] ?? "text-grey-400")} />
          {guarantee.status}
        </span>
      </header>

      <footer className="flex items-center justify-between gap-3">
        <span className="text-body-sm whitespace-nowrap text-grey-900">{term}</span>
        <Link href={`/dashboard/guarantees/${guarantee.instrument_id}`}>
          <Button variant="outline" size="md" className="rounded-pill px-7">
            View
          </Button>
        </Link>
      </footer>
    </article>
  );
}

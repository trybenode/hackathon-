import Link from "next/link";
import { Button, ClockIcon, DotIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { formatExpiresIn, formatRelative } from "@/lib/format";
import type { GuaranteeCard as Guarantee } from "@/lib/guarantor";
import { WorkerAvatar } from "./WorkerAvatar";

type RequestBucket = NonNullable<Guarantee["request_bucket"]>;

const LABEL: Record<RequestBucket, string> = {
  pending: "Pending",
  accepted: "Accepted",
  declined: "Declined",
};

const DOT: Record<RequestBucket, string> = {
  pending: "text-warning",
  accepted: "text-success",
  declined: "text-error-mid",
};

/** A request on the Pending / Accepted / Declined tabs. */
export function RequestCard({ request }: { request: Guarantee }) {
  const bucket = request.request_bucket ?? "pending";
  const expiry = bucket === "pending" ? formatExpiresIn(request.valid_until) : null;

  const when =
    bucket === "pending"
      ? `Requested - ${formatRelative(request.requested_at)}`
      : `${LABEL[bucket]} - ${request.responded_at ? formatRelative(request.responded_at) : "—"}`;

  // Accepting means reading the terms, signing and passing the identity
  // checks, so it opens the review screen rather than accepting in one tap.
  // An accepted request whose checks are unfinished goes back to that flow;
  // a live one has a details page. A declined one has nowhere to go.
  const action =
    bucket === "pending"
      ? { label: "Accept", href: `/guarantor/${request.instrument_id}/review` }
      : bucket === "accepted"
        ? {
            label: "View",
            href:
              request.bucket === "request"
                ? `/guarantor/${request.instrument_id}/review`
                : `/dashboard/guarantees/${request.instrument_id}`,
          }
        : null;

  return (
    <article className="flex flex-col gap-6 rounded-xl border border-stroke bg-white p-4 shadow-1">
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <WorkerAvatar name={request.worker_name} src={request.avatar_url} />
          <span className="flex flex-col">
            <span className="text-body-md text-grey-900">{request.worker_name}</span>
            <span className="text-body-sm text-grey-600">{request.worker_role ?? ""}</span>
          </span>
        </div>
        <span className="flex items-center gap-1.5 text-body-sm text-grey-900">
          <DotIcon className={cn("shrink-0", DOT[bucket])} />
          {LABEL[bucket]}
        </span>
      </header>

      <div className="flex flex-col gap-4">
        <div className="flex min-h-10 items-center justify-between gap-4">
          <span className="text-body-sm text-grey-900">{when}</span>
          {action && (
            <Link href={action.href}>
              <Button variant="outline" size="md" className="rounded-pill px-8">
                {action.label}
              </Button>
            </Link>
          )}
        </div>
        {expiry && (
          <p className="flex items-center gap-2 text-body-sm text-grey-900">
            <ClockIcon className="shrink-0 text-grey-600" />
            {expiry}
          </p>
        )}
      </div>
    </article>
  );
}

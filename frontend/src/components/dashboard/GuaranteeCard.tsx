import Image from "next/image";
import Link from "next/link";
import { Button, DotIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { formatNaira, formatStartedOn } from "@/lib/format";
import type { GuaranteeCard as Guarantee } from "@/lib/guarantor";

/** Initials stand in until workers have avatars. */
function initialsOf(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/**
 * Each outcome gets its own colour so a claim that was paid out does not read
 * the same as one that was dismissed.
 */
const statusDot: Record<string, string> = {
  Active: "text-success",
  Completed: "text-success",
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

export function GuaranteeCard({
  guarantee,
  layout = "stacked",
}: {
  guarantee: Guarantee;
  /** `stacked` puts View on the left (home), `inline` puts it on the right. */
  layout?: "stacked" | "inline";
}) {
  const view = (
    <Link href={`/guarantor/${guarantee.instrument_id}/review`}>
      <Button variant="outline" size="md" className="rounded-pill px-8">
        View
      </Button>
    </Link>
  );
  const started = (
    <span className="text-body-sm text-grey-600">
      Started - {formatStartedOn(guarantee.started_on)}
    </span>
  );

  return (
    <article className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4 shadow-1">
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-pill bg-badge-high text-body-sm font-semibold text-grey-900">
            {guarantee.avatar_url ? (
              <Image
                src={guarantee.avatar_url}
                alt=""
                width={44}
                height={44}
                unoptimized
                className="h-11 w-11 object-cover"
              />
            ) : (
              initialsOf(guarantee.worker_name)
            )}
          </span>
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

      <div className="flex flex-col gap-1">
        <p className="text-body-lg font-semibold text-grey-900">
          {guarantee.job_title ?? "Guarantee"}
        </p>
        <p className="text-body-sm text-grey-600">{formatNaira(guarantee.amount)}</p>
      </div>

      <footer className="flex items-center justify-between gap-4">
        {layout === "inline" ? (
          <>
            {started}
            {view}
          </>
        ) : (
          <>
            {view}
            {started}
          </>
        )}
      </footer>
    </article>
  );
}

import Image from "next/image";
import { Button, DotIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { formatNaira, type DashboardGuarantee } from "@/lib/dashboardMock";

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

export function GuaranteeCard({
  guarantee,
  layout = "stacked",
}: {
  guarantee: DashboardGuarantee;
  /** `stacked` puts View on the left (home), `inline` puts it on the right. */
  layout?: "stacked" | "inline";
}) {
  const active = guarantee.status === "Active";

  return (
    <article className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4 shadow-1">
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-pill bg-badge-high text-body-sm font-semibold text-grey-900">
            {guarantee.avatarUrl ? (
              <Image
                src={guarantee.avatarUrl}
                alt=""
                width={44}
                height={44}
                unoptimized
                className="h-11 w-11 object-cover"
              />
            ) : (
              initialsOf(guarantee.workerName)
            )}
          </span>
          <span className="flex flex-col">
            <span className="text-body-md font-medium text-grey-900">{guarantee.workerName}</span>
            <span className="text-body-sm text-grey-600">{guarantee.workerRole}</span>
          </span>
        </div>

        <span className="flex items-center gap-1.5 text-body-sm text-grey-900">
          <DotIcon className={cn("shrink-0", active ? "text-success" : "text-success")} />
          {guarantee.status}
        </span>
      </header>

      <div className="flex flex-col gap-1">
        <p className="text-body-lg font-semibold text-grey-900">{guarantee.jobTitle}</p>
        <p className="text-body-sm text-grey-600">{formatNaira(guarantee.amount)}</p>
      </div>

      <footer className="flex items-center justify-between gap-4">
        {layout === "inline" ? (
          <>
            <span className="text-body-sm text-grey-600">Started - {guarantee.startedOn}</span>
            <Button variant="outline" size="md" className="rounded-pill px-8">
              View
            </Button>
          </>
        ) : (
          <>
            <Button variant="outline" size="md" className="rounded-pill px-8">
              View
            </Button>
            <span className="text-body-sm text-grey-600">Started - {guarantee.startedOn}</span>
          </>
        )}
      </footer>
    </article>
  );
}

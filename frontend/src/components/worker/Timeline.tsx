import { cn } from "@/lib/cn";

export type TimelineStep = {
  label: string;
  /** Done steps carry when they happened; pending ones show a dash. */
  at?: string | null;
  /** A line under the time saying what happened, as the landing page shows. */
  note?: string;
  state: "done" | "current" | "pending";
};

/**
 * The vertical progress track on Job Details and the escrow screens.
 *
 * Done steps are a filled dot with a soft halo, the current step is a hollow
 * ring, pending steps are grey. The connector is cyan up to the last done
 * step and grey after it.
 */
export function Timeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol className="flex flex-col pl-6">
      {steps.map((step, index) => {
        const last = index === steps.length - 1;
        const next = steps[index + 1];
        // The line below a step is lit only when the following step has begun.
        const lineLit = step.state === "done" && next && next.state !== "pending";

        return (
          <li key={step.label} className="relative flex gap-4 pb-8 last:pb-6">
            {!last && (
              <span
                aria-hidden
                className={cn(
                  "absolute top-3.5 left-[6px] h-full w-0.5",
                  lineLit ? "bg-primary-300" : "bg-grey-200",
                )}
              />
            )}
            {/* The dot also continues the line one step past the end, as the
                designs do. */}
            {last && (
              <span
                aria-hidden
                className={cn(
                  "absolute top-3.5 left-[6px] h-8 w-0.5",
                  step.state === "done" ? "bg-primary-300" : "bg-grey-200",
                )}
              />
            )}

            <span
              aria-hidden
              className={cn(
                "relative z-10 mt-1 h-3.5 w-3.5 shrink-0 rounded-pill",
                step.state === "done" && "bg-primary-300 ring-4 ring-primary-50",
                step.state === "current" && "border-2 border-primary-400 bg-white",
                step.state === "pending" && "bg-grey-200",
              )}
            />

            <div className="flex flex-col gap-0.5">
              <span
                className={cn(
                  "text-body-md",
                  step.state === "pending" ? "text-grey-400" : "text-grey-900",
                )}
              >
                {step.label}
              </span>
              <span
                className={cn(
                  "text-xs leading-4",
                  step.state === "pending" ? "text-grey-400" : "text-navy-300",
                )}
              >
                {step.at ?? "· —"}
              </span>
              {step.note && <span className="text-xs leading-4 text-navy-300">{step.note}</span>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

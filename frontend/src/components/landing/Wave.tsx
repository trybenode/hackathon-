import { cn } from "@/lib/cn";

/**
 * One edge of the problem band. As in the design, both edges share one
 * shape, rising gently left to right: a soft bend near each side and level
 * across the middle. "top" fills below the edge, "bottom" fills above it.
 */
const EDGE = "M0 64C150 38 250 30 360 29H1150C1300 27 1380 14 1440 0";

export function Wave({ edge, className }: { edge: "top" | "bottom"; className?: string }) {
  return (
    <svg
      viewBox="0 0 1440 64"
      preserveAspectRatio="none"
      aria-hidden
      className={cn("block h-8 w-full text-primary-50 lg:h-16", className)}
    >
      <path fill="currentColor" d={edge === "top" ? `${EDGE}V64Z` : `${EDGE}H0Z`} />
    </svg>
  );
}

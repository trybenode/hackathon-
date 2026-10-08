import { cn } from "@/lib/cn";
import { formatPercent } from "@/lib/workerRecord";

/** The trust score as a filled ring with the percentage in the middle. */
export function ScoreRing({
  score,
  size = 80,
  thickness = 8,
  className,
}: {
  /** 0 to 1, or null when there is no score yet. */
  score: number | null;
  size?: number;
  thickness?: number;
  className?: string;
}) {
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = score === null ? 0 : Math.min(1, Math.max(0, score)) * circumference;
  const label = score === null ? "—" : formatPercent(score);

  return (
    <span
      role="img"
      aria-label={score === null ? "No trust score yet" : `Trust score ${label}`}
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={thickness}
          className="stroke-grey-200"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={thickness}
          strokeDasharray={`${filled} ${circumference}`}
          className="stroke-primary-400"
        />
      </svg>
      {/* Small rings size the label to the ring, so "100%" still clears the
          stroke with room to spare, as in the designs. */}
      <span
        className={cn(
          "absolute leading-none text-grey-800 tabular-nums",
          size >= 64 && "text-body-lg font-medium",
        )}
        style={size >= 64 ? undefined : { fontSize: Math.round(size * 0.27) }}
      >
        {label}
      </span>
    </span>
  );
}

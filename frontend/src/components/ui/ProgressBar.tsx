import { cn } from "@/lib/cn";

export type ProgressTone = "primary" | "success" | "warning" | "error";

const fillClasses: Record<ProgressTone, string> = {
  primary: "bg-primary-400",
  success: "bg-success-mid",
  warning: "bg-warning",
  error: "bg-error",
};

const labelClasses: Record<ProgressTone, string> = {
  primary: "text-primary-500",
  success: "text-success",
  warning: "text-warning",
  error: "text-error",
};

export type ProgressBarProps = {
  /** 0–100. Values outside the range are clamped. */
  value: number;
  tone?: ProgressTone;
  /** Show the percentage to the right of the bar. */
  showValue?: boolean;
  /** Describes what is progressing, for screen readers. */
  label?: string;
  /** Break the filled part into segments, as the upload bar does. */
  segmented?: boolean;
  className?: string;
};

/** Gaps punched out of the fill, so the track shows through. */
const segmentStyle = {
  maskImage: "repeating-linear-gradient(to right, black 0 34px, transparent 34px 35px)",
  WebkitMaskImage: "repeating-linear-gradient(to right, black 0 34px, transparent 34px 35px)",
};

export function ProgressBar({
  value,
  tone = "primary",
  showValue = false,
  label,
  segmented = false,
  className,
}: ProgressBarProps) {
  const percent = Math.round(Math.min(100, Math.max(0, value)));

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-1.5 flex-1 overflow-hidden rounded-pill bg-grey-200"
      >
        <div
          className={cn("h-full transition-all", !segmented && "rounded-pill", fillClasses[tone])}
          style={{ width: `${percent}%`, ...(segmented ? segmentStyle : null) }}
        />
      </div>
      {showValue && (
        <span className={cn("shrink-0 text-xs leading-4 font-medium", labelClasses[tone])}>
          {percent}%
        </span>
      )}
    </div>
  );
}

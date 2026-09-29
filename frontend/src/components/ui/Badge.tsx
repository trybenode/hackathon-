import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { DotIcon } from "./icons";

export type BadgeTone =
  /* Named after the designs */
  | "high"
  | "medium"
  | "low"
  | "verified"
  | "pending"
  | "failed"
  /* Generic fallbacks */
  | "success"
  | "warning"
  | "error"
  | "info"
  | "neutral";

const toneClasses: Record<BadgeTone, string> = {
  high: "bg-badge-high text-success",
  medium: "bg-badge-medium text-badge-medium-text",
  low: "bg-badge-low text-error",
  verified: "bg-badge-verified text-info",
  pending: "bg-badge-pending text-badge-pending-text",
  failed: "bg-error-light text-error",
  success: "bg-success-light text-success",
  warning: "bg-warning-light text-badge-medium-text",
  error: "bg-error-light text-error",
  info: "bg-info-light text-info",
  neutral: "bg-grey-200 text-grey-600",
};

export type BadgeProps = ComponentProps<"span"> & {
  tone?: BadgeTone;
  /** Leading icon. Ignored when `dot` is set. */
  icon?: ReactNode;
  /** Show a small filled circle instead of an icon. */
  dot?: boolean;
};

export function Badge({
  tone = "neutral",
  icon,
  dot = false,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-xs leading-4 font-medium",
        toneClasses[tone],
        className,
      )}
      {...props}
    >
      {dot ? <DotIcon className="shrink-0" /> : icon && <span className="flex shrink-0">{icon}</span>}
      {children}
    </span>
  );
}

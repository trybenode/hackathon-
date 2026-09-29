import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";
import { DotIcon } from "./icons";

export type Status =
  | "active"
  | "completed"
  | "pending"
  | "cancelled"
  | "failed"
  | "suspended"
  | "processing"
  | "expired";

const dotClasses: Record<Status, string> = {
  active: "text-success",
  completed: "text-success",
  pending: "text-warning",
  cancelled: "text-grey-400",
  failed: "text-error",
  suspended: "text-error",
  processing: "text-info",
  expired: "text-grey-800",
};

const defaultLabels: Record<Status, string> = {
  active: "Active",
  completed: "Completed",
  pending: "Pending",
  cancelled: "Cancelled",
  failed: "Failed",
  suspended: "Suspended",
  processing: "Processing",
  expired: "Expired",
};

export type StatusBadgeProps = Omit<ComponentProps<"span">, "children"> & {
  status: Status;
  /** Overrides the default label for the status. */
  children?: React.ReactNode;
};

/** A colored dot with a label, for general record status. */
export function StatusBadge({ status, className, children, ...props }: StatusBadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center gap-2 text-body-sm text-grey-900", className)}
      {...props}
    >
      <DotIcon className={cn("shrink-0", dotClasses[status])} />
      {children ?? defaultLabels[status]}
    </span>
  );
}

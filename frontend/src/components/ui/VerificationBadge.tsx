import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { CheckIcon, ClockIcon, CloseIcon, ExclamationIcon } from "./icons";

export type VerificationStatus = "verified" | "pending" | "failed" | "needs-review";

const icons: Record<VerificationStatus, ReactNode> = {
  verified: <CheckIcon className="text-success" />,
  pending: <ClockIcon className="text-warning" />,
  failed: <CloseIcon className="text-error-mid" strokeWidth="2" />,
  "needs-review": <ExclamationIcon className="text-orange" />,
};

const defaultLabels: Record<VerificationStatus, string> = {
  verified: "Verified",
  pending: "Pending",
  failed: "Failed",
  "needs-review": "Needs review",
};

export type VerificationBadgeProps = Omit<ComponentProps<"span">, "children"> & {
  status: VerificationStatus;
  /** Overrides the default label for the status. */
  children?: ReactNode;
};

/** A grey pill with a colored status icon, for verification state. */
export function VerificationBadge({
  status,
  className,
  children,
  ...props
}: VerificationBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-pill bg-grey-50 px-3 py-1.5 text-body-sm text-grey-900",
        className,
      )}
      {...props}
    >
      <span className="flex shrink-0">{icons[status]}</span>
      {children ?? defaultLabels[status]}
    </span>
  );
}

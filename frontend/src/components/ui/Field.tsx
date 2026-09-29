import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { CheckCircleIcon, ErrorCircleIcon } from "./icons";

export type FieldStatus = "default" | "success" | "error";
export type FieldSize = "md" | "lg";
export type LabelPlacement = "outside" | "inside";

/** Props every form control shares. */
export type FieldBaseProps = {
  label?: ReactNode;
  /** Shown under the control. Rendered as the error message when `status="error"`. */
  helperText?: ReactNode;
  status?: FieldStatus;
  size?: FieldSize;
};

const statusBoxClasses: Record<FieldStatus, string> = {
  default:
    "text-grey-900 border-stroke hover:not-focus-within:bg-grey-200 hover:not-focus-within:border-grey-200 " +
    "focus-within:border-primary-300 focus-within:ring-1 focus-within:ring-primary-300",
  success: "border-success-light ring-1 ring-success-light text-success",
  error: "border-error-light ring-1 ring-error-light text-error",
};

const sizeBoxClasses: Record<FieldSize, string> = {
  md: "min-h-10 px-3 text-body-sm",
  lg: "min-h-13 px-4 text-body-md",
};

/** Classes for the bordered box that wraps a control and its icons. */
export function fieldBoxClasses({
  status = "default",
  size = "md",
  disabled,
  active,
}: {
  status?: FieldStatus;
  size?: FieldSize;
  disabled?: boolean;
  /** Force the focused look, e.g. while a dropdown menu is open. */
  active?: boolean;
}) {
  return cn(
    "group relative flex w-full gap-2 rounded-md border transition-colors",
    sizeBoxClasses[size],
    disabled
      ? "cursor-not-allowed border-transparent bg-grey-200 text-grey-400"
      : cn(
          "bg-white",
          active && status === "default"
            ? "text-grey-900 border-primary-300 ring-1 ring-primary-300"
            : statusBoxClasses[status],
        ),
  );
}

/** Text classes for the native input/textarea inside a field box. */
export const controlClasses =
  "w-full min-w-0 bg-transparent text-inherit outline-none placeholder:text-grey-400 disabled:cursor-not-allowed";

export function StatusIcon({ status }: { status: FieldStatus }) {
  if (status === "success") return <CheckCircleIcon className="shrink-0 text-success" />;
  if (status === "error") return <ErrorCircleIcon className="shrink-0 text-error" />;
  return null;
}

export function helperId(id: string) {
  return `${id}-helper`;
}

type FieldProps = {
  id: string;
  label?: ReactNode;
  /** Right-aligned next to the label, e.g. a character counter. */
  labelAside?: ReactNode;
  helperText?: ReactNode;
  status?: FieldStatus;
  disabled?: boolean;
  className?: string;
  children: ReactNode;
};

/** Label + control + helper text layout shared by all inputs. */
export function Field({
  id,
  label,
  labelAside,
  helperText,
  status = "default",
  disabled,
  className,
  children,
}: FieldProps) {
  return (
    <div className={cn("flex w-full flex-col gap-2", className)}>
      {(label || labelAside) && (
        <div className="flex items-center justify-between gap-2 text-body-sm leading-5 text-grey-600">
          {label && (
            <label htmlFor={id} className={cn("font-medium", disabled && "text-grey-400")}>
              {label}
            </label>
          )}
          {labelAside && <span className="ml-auto">{labelAside}</span>}
        </div>
      )}
      {children}
      {helperText && (
        <p
          id={helperId(id)}
          className={cn(
            "text-body-sm leading-5",
            disabled ? "text-grey-400" : status === "error" ? "text-error" : "text-grey-600",
          )}
        >
          {helperText}
        </p>
      )}
    </div>
  );
}

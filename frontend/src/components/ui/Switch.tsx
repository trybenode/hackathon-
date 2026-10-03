"use client";

import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type SwitchProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Text beside the switch. Clicking it toggles too. */
  label?: ReactNode;
  disabled?: boolean;
  id?: string;
  className?: string;
};

/** An on/off toggle, built on a checkbox so it stays keyboard accessible. */
export function Switch({
  checked,
  onChange,
  label,
  disabled = false,
  id: idProp,
  className,
}: SwitchProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="peer sr-only"
      />
      <label
        htmlFor={id}
        aria-hidden
        className={cn(
          "relative h-6 w-11 shrink-0 rounded-pill transition-colors",
          "peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 peer-focus-visible:ring-offset-2",
          disabled ? "cursor-not-allowed bg-grey-200" : "cursor-pointer",
          !disabled && (checked ? "bg-primary-500" : "bg-grey-400"),
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 h-5 w-5 rounded-pill bg-white shadow-1 transition-transform",
            checked && "translate-x-5",
          )}
        />
      </label>
      {label && (
        <label
          htmlFor={id}
          className={cn(
            "text-body-sm",
            disabled ? "cursor-not-allowed text-grey-400" : "cursor-pointer text-grey-900",
          )}
        >
          {label}
        </label>
      )}
    </div>
  );
}

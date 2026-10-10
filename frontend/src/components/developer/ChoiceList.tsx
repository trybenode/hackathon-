"use client";

import { useId } from "react";
import { cn } from "@/lib/cn";

/** Radio options as the developer screens draw them: a filled check when chosen. */
export function ChoiceList<T extends string>({
  legend,
  options,
  value,
  onChange,
}: {
  legend: string;
  options: readonly { value: T; label: string }[];
  value: T | null;
  onChange: (value: T) => void;
}) {
  const name = useId();

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="pb-3 text-body-sm font-medium text-grey-600">{legend}</legend>
      {options.map((option) => {
        const id = `${name}-${option.value}`;
        const checked = value === option.value;
        return (
          <label key={option.value} htmlFor={id} className="flex cursor-pointer items-center gap-3">
            <input
              id={id}
              type="radio"
              name={name}
              value={option.value}
              checked={checked}
              onChange={() => onChange(option.value)}
              className="peer sr-only"
            />
            <span
              aria-hidden
              className={cn(
                "flex h-5 w-5 shrink-0 items-center justify-center rounded-pill transition-colors",
                "peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 peer-focus-visible:ring-offset-2",
                checked ? "bg-primary-500 text-white" : "border border-grey-200 bg-grey-50",
              )}
            >
              {checked && (
                <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m3.5 8.5 3 3 6-7" />
                </svg>
              )}
            </span>
            <span className="text-body-md text-grey-900">{option.label}</span>
          </label>
        );
      })}
    </fieldset>
  );
}

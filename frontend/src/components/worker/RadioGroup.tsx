"use client";

import { useId } from "react";
import { cn } from "@/lib/cn";

/**
 * A vertical list of radio options, as on "Report an issue".
 *
 * The design system has no radio yet; this lives with the worker screens until
 * it is promoted into components/ui.
 */
export function RadioGroup<T extends string>({
  options,
  value,
  onChange,
  legend,
}: {
  options: readonly T[];
  value: T | null;
  onChange: (value: T) => void;
  legend: string;
}) {
  const name = useId();

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="sr-only">{legend}</legend>
      {options.map((option) => {
        const id = `${name}-${option}`;
        const checked = value === option;

        return (
          <label key={option} htmlFor={id} className="flex cursor-pointer items-center gap-3">
            <input
              id={id}
              type="radio"
              name={name}
              value={option}
              checked={checked}
              onChange={() => onChange(option)}
              className="peer sr-only"
            />
            <span
              aria-hidden
              className={cn(
                "h-[18px] w-[18px] shrink-0 rounded-pill border transition-colors",
                "peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 peer-focus-visible:ring-offset-2",
                checked ? "border-[5px] border-primary-400" : "border-grey-400",
              )}
            />
            <span className="text-body-md text-grey-900">{option}</span>
          </label>
        );
      })}
    </fieldset>
  );
}

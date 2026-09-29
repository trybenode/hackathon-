"use client";

import { useId, useState, type ComponentProps } from "react";
import { cn } from "@/lib/cn";
import {
  Field,
  controlClasses,
  fieldBoxClasses,
  helperId,
  type FieldBaseProps,
  type LabelPlacement,
} from "./Field";

export type TextareaProps = ComponentProps<"textarea"> &
  FieldBaseProps & {
    labelPlacement?: LabelPlacement;
    /** Show a "length/maxLength" counter beside the label. */
    showCount?: boolean;
    wrapperClassName?: string;
  };

export function Textarea({
  id: idProp,
  label,
  labelPlacement = "outside",
  helperText,
  status = "default",
  size = "md",
  showCount = false,
  maxLength,
  rows = 5,
  disabled,
  value,
  defaultValue,
  onChange,
  className,
  wrapperClassName,
  ...props
}: TextareaProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const labelInside = labelPlacement === "inside" && Boolean(label);

  const [uncontrolledLength, setUncontrolledLength] = useState(String(defaultValue ?? "").length);
  const length = value !== undefined ? String(value).length : uncontrolledLength;
  const counter = showCount ? (maxLength ? `${length}/${maxLength}` : `${length}`) : undefined;

  return (
    <Field
      id={id}
      label={labelInside ? undefined : label}
      labelAside={labelInside ? undefined : counter}
      helperText={helperText}
      status={status}
      disabled={disabled}
      className={wrapperClassName}
    >
      <div className={cn(fieldBoxClasses({ status, size, disabled }), "flex-col gap-1 py-2")}>
        {labelInside && (
          <div className="flex justify-between gap-2 text-body-sm leading-5 text-grey-600">
            <label htmlFor={id} className={cn(disabled && "text-grey-400")}>
              {label}
            </label>
            {counter && <span>{counter}</span>}
          </div>
        )}
        <textarea
          id={id}
          rows={rows}
          maxLength={maxLength}
          disabled={disabled}
          value={value}
          defaultValue={defaultValue}
          onChange={(event) => {
            setUncontrolledLength(event.target.value.length);
            onChange?.(event);
          }}
          aria-invalid={status === "error" || undefined}
          aria-describedby={helperText ? helperId(id) : undefined}
          className={cn(controlClasses, "resize-none", className)}
          {...props}
        />
      </div>
    </Field>
  );
}

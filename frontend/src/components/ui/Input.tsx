"use client";

import { useId, type ComponentProps, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import {
  Field,
  StatusIcon,
  controlClasses,
  fieldBoxClasses,
  helperId,
  type FieldBaseProps,
  type LabelPlacement,
} from "./Field";

export type InputProps = Omit<ComponentProps<"input">, "size"> &
  FieldBaseProps & {
    /** `inside` floats the label inside the box, above the value. */
    labelPlacement?: LabelPlacement;
    leadingIcon?: ReactNode;
    /** Replaced by the status icon when `status` is success or error. */
    trailingIcon?: ReactNode;
    /** Fixed lead segment before a divider, e.g. "https://" or "+234" (grouped input). */
    lead?: ReactNode;
    /** Applied to the outer wrapper (label + box + helper). */
    wrapperClassName?: string;
  };

export function Input({
  id: idProp,
  label,
  labelPlacement = "outside",
  helperText,
  status = "default",
  size = "md",
  leadingIcon,
  trailingIcon,
  lead,
  disabled,
  placeholder,
  className,
  wrapperClassName,
  ...props
}: InputProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const labelInside = labelPlacement === "inside" && Boolean(label);
  const trailing = status === "default" ? trailingIcon : <StatusIcon status={status} />;

  return (
    <Field
      id={id}
      label={labelInside ? undefined : label}
      helperText={helperText}
      status={status}
      disabled={disabled}
      className={wrapperClassName}
    >
      <div className={cn(fieldBoxClasses({ status, size, disabled }), "items-center")}>
        {leadingIcon && <span className="flex shrink-0 text-inherit">{leadingIcon}</span>}
        {lead && (
          <>
            <span className="shrink-0 group-has-[input:placeholder-shown]:text-grey-400">{lead}</span>
            <span aria-hidden className="h-5 w-px shrink-0 bg-stroke" />
          </>
        )}
        <div className={cn("relative flex flex-1 self-stretch", labelInside && "pt-4")}>
          <input
            id={id}
            disabled={disabled}
            // A placeholder is required for the floating label's :placeholder-shown check.
            placeholder={labelInside ? (placeholder ?? " ") : placeholder}
            aria-invalid={status === "error" || undefined}
            aria-describedby={helperText ? helperId(id) : undefined}
            className={cn(controlClasses, "peer", labelInside && "placeholder:text-transparent", className)}
            {...props}
          />
          {labelInside && (
            <label
              htmlFor={id}
              className={cn(
                "pointer-events-none absolute left-0 top-1.5 text-xs leading-4 text-grey-600 transition-all",
                // Empty and unfocused: sit in the middle like a placeholder.
                "peer-[:placeholder-shown:not(:focus)]:top-1/2 peer-[:placeholder-shown:not(:focus)]:-translate-y-1/2",
                "peer-[:placeholder-shown:not(:focus)]:text-[length:inherit]",
                disabled && "text-grey-400",
              )}
            >
              {label}
            </label>
          )}
        </div>
        {trailing && <span className="flex shrink-0 text-inherit">{trailing}</span>}
      </div>
    </Field>
  );
}

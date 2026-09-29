"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";
import { Field, StatusIcon, fieldBoxClasses, helperId, type FieldBaseProps } from "./Field";
import { CaretDownIcon, CloseIcon } from "./icons";

export type SelectOption = {
  value: string;
  label: ReactNode;
  icon?: ReactNode;
  disabled?: boolean;
};

export type SelectProps = FieldBaseProps & {
  options: SelectOption[];
  /** Controlled value. Pass `null` for no selection. */
  value?: string | null;
  defaultValue?: string | null;
  onChange?: (value: string | null) => void;
  placeholder?: string;
  leadingIcon?: ReactNode;
  /** Show a clear (×) button when a value is selected. */
  clearable?: boolean;
  disabled?: boolean;
  /** Submits the value with a surrounding <form>. */
  name?: string;
  id?: string;
  className?: string;
};

export function Select({
  options,
  value: valueProp,
  defaultValue = null,
  onChange,
  placeholder = "Select an option",
  label,
  helperText,
  status = "default",
  size = "md",
  leadingIcon,
  clearable = false,
  disabled,
  name,
  id: idProp,
  className,
}: SelectProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const listboxId = `${id}-listbox`;

  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);
  const value = valueProp !== undefined ? valueProp : uncontrolledValue;
  const selected = options.find((option) => option.value === value);

  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open]);

  const setValue = (next: string | null) => {
    if (valueProp === undefined) setUncontrolledValue(next);
    onChange?.(next);
  };

  const openMenu = () => {
    if (disabled) return;
    const selectedIndex = options.findIndex((option) => option.value === value);
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : nextEnabled(-1, 1));
    setOpen(true);
  };

  const choose = (option: SelectOption) => {
    if (option.disabled) return;
    setValue(option.value);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const nextEnabled = (from: number, step: 1 | -1) => {
    for (let i = from + step; i >= 0 && i < options.length; i += step) {
      if (!options[i].disabled) return i;
    }
    return from;
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        openMenu();
      }
      return;
    }
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setActiveIndex((i) => nextEnabled(i, 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        setActiveIndex((i) => nextEnabled(i, -1));
        break;
      case "Home":
        event.preventDefault();
        setActiveIndex(nextEnabled(-1, 1));
        break;
      case "End":
        event.preventDefault();
        setActiveIndex(nextEnabled(options.length, -1));
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        if (options[activeIndex]) choose(options[activeIndex]);
        break;
      case "Escape":
        event.preventDefault();
        setOpen(false);
        break;
      case "Tab":
        setOpen(false);
        break;
    }
  };

  const describedBy = helperText ? helperId(id) : undefined;

  return (
    <Field
      id={id}
      label={label}
      helperText={helperText}
      status={status}
      disabled={disabled}
      className={className}
    >
      <div ref={rootRef} className="relative">
        <div className={cn(fieldBoxClasses({ status, size, disabled, active: open }), "items-center")}>
          <button
            ref={triggerRef}
            id={id}
            type="button"
            role="combobox"
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-activedescendant={open && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
            aria-invalid={status === "error" || undefined}
            aria-describedby={describedBy}
            disabled={disabled}
            onClick={() => (open ? setOpen(false) : openMenu())}
            onKeyDown={handleKeyDown}
            className="flex min-w-0 flex-1 items-center gap-2 self-stretch text-left outline-none disabled:cursor-not-allowed"
          >
            {(selected?.icon ?? leadingIcon) && (
              <span className="flex shrink-0">{selected?.icon ?? leadingIcon}</span>
            )}
            <span className={cn("truncate", !selected && "text-grey-400")}>
              {selected ? selected.label : placeholder}
            </span>
          </button>

          {clearable && selected && !disabled && (
            <>
              <button
                type="button"
                aria-label="Clear selection"
                onClick={() => {
                  setValue(null);
                  triggerRef.current?.focus();
                }}
                className="flex shrink-0 rounded-sm text-grey-600 outline-none hover:text-grey-900 focus-visible:ring-2 focus-visible:ring-primary-300"
              >
                <CloseIcon />
              </button>
              <span aria-hidden className="h-5 w-px shrink-0 bg-grey-200" />
            </>
          )}

          <StatusIcon status={status} />
          <CaretDownIcon
            onClick={() => triggerRef.current?.click()}
            className={cn(
              "shrink-0 cursor-pointer text-grey-900 transition-transform",
              disabled && "cursor-not-allowed text-grey-400",
              open && "rotate-180",
            )}
          />
        </div>

        {open && (
          <ul
            id={listboxId}
            role="listbox"
            aria-labelledby={id}
            className="absolute inset-x-0 top-full z-20 mt-1 max-h-60 overflow-auto rounded-md border border-grey-200 bg-white py-2 shadow-2"
          >
            {options.map((option, index) => (
              <li
                key={option.value}
                id={`${id}-option-${index}`}
                role="option"
                aria-selected={option.value === value}
                aria-disabled={option.disabled || undefined}
                onPointerDown={(event) => event.preventDefault()}
                onClick={() => choose(option)}
                onMouseEnter={() => !option.disabled && setActiveIndex(index)}
                className={cn(
                  "flex cursor-pointer items-center gap-2 px-3 py-1.5 text-grey-900",
                  size === "lg" ? "text-body-md" : "text-body-sm",
                  index === activeIndex && "bg-grey-50",
                  option.value === value && "bg-primary-50",
                  option.disabled && "cursor-not-allowed text-grey-400",
                )}
              >
                {option.icon && <span className="flex shrink-0">{option.icon}</span>}
                {option.label}
              </li>
            ))}
          </ul>
        )}
      </div>

      {name && <input type="hidden" name={name} value={value ?? ""} />}
    </Field>
  );
}

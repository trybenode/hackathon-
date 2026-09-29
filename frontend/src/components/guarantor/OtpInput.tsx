"use client";

import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";

export type OtpInputProps = {
  value: string;
  onChange: (value: string) => void;
  length?: number;
  disabled?: boolean;
  /** Fired once the last box is filled, so the form can submit itself. */
  onComplete?: (value: string) => void;
};

/** Boxed one-time-code entry that behaves like a single field. */
export function OtpInput({
  value,
  onChange,
  length = 6,
  disabled = false,
  onComplete,
}: OtpInputProps) {
  const boxes = useRef<(HTMLInputElement | null)[]>([]);
  const digits = Array.from({ length }, (_, index) => value[index] ?? "");

  function set(next: string) {
    const trimmed = next.slice(0, length);
    onChange(trimmed);
    if (trimmed.length === length) onComplete?.(trimmed);
  }

  function handleInput(index: number, raw: string) {
    const digit = raw.replace(/\D/g, "").slice(-1);
    if (!digit) return;

    const next = (value.slice(0, index) + digit + value.slice(index + 1)).slice(0, length);
    set(next);
    boxes.current[Math.min(index + 1, length - 1)]?.focus();
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace") {
      event.preventDefault();
      // Clear this box, or step back when it is already empty.
      const target = value[index] ? index : Math.max(index - 1, 0);
      set(value.slice(0, target) + value.slice(target + 1));
      boxes.current[target]?.focus();
    }
    if (event.key === "ArrowLeft") boxes.current[Math.max(index - 1, 0)]?.focus();
    if (event.key === "ArrowRight") boxes.current[Math.min(index + 1, length - 1)]?.focus();
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "");
    if (!pasted) return;

    event.preventDefault();
    set(pasted.slice(0, length));
    boxes.current[Math.min(pasted.length, length - 1)]?.focus();
  }

  return (
    <div className="flex justify-between gap-2">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(node) => {
            boxes.current[index] = node;
          }}
          value={digit}
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          aria-label={`Digit ${index + 1}`}
          disabled={disabled}
          onChange={(event) => handleInput(index, event.target.value)}
          onKeyDown={(event) => handleKeyDown(index, event)}
          onPaste={handlePaste}
          onFocus={(event) => event.target.select()}
          className={cn(
            "h-14 w-12 rounded-lg border text-center text-h3 text-grey-900 outline-none transition-colors",
            digit
              ? "border-primary-300 bg-white"
              : "border-stroke bg-grey-200 text-grey-400",
            "focus:border-primary-400 focus:ring-1 focus:ring-primary-300",
            disabled && "cursor-not-allowed opacity-60",
          )}
        />
      ))}
    </div>
  );
}

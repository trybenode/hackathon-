"use client";

import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";

/** Payscrow's escrow codes are 6 letters and digits (e.g. 5Z093S). */
export const ESCROW_CODE_LENGTH = 6;

/**
 * Boxed entry for the escrow code, in two groups of three, behaving like one
 * field: typing moves forward, backspace moves back, pasting fills it.
 */
export function EscrowCodeInput({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const boxes = useRef<(HTMLInputElement | null)[]>([]);
  const chars = Array.from({ length: ESCROW_CODE_LENGTH }, (_, index) => value[index] ?? "");

  const clean = (raw: string) => raw.replace(/[^a-z0-9]/gi, "").toUpperCase();

  function handleInput(index: number, raw: string) {
    const char = clean(raw).slice(-1);
    if (!char) return;
    onChange((value.slice(0, index) + char + value.slice(index + 1)).slice(0, ESCROW_CODE_LENGTH));
    boxes.current[Math.min(index + 1, ESCROW_CODE_LENGTH - 1)]?.focus();
  }

  function handleKey(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Backspace") return;
    event.preventDefault();
    if (value[index]) {
      onChange(value.slice(0, index) + value.slice(index + 1));
    } else if (index > 0) {
      onChange(value.slice(0, index - 1) + value.slice(index));
      boxes.current[index - 1]?.focus();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    event.preventDefault();
    const pasted = clean(event.clipboardData.getData("text")).slice(0, ESCROW_CODE_LENGTH);
    onChange(pasted);
    boxes.current[Math.min(pasted.length, ESCROW_CODE_LENGTH - 1)]?.focus();
  }

  return (
    <div className="flex items-center justify-between gap-1" role="group" aria-label="Escrow code">
      {chars.map((char, index) => (
        <span key={index} className="contents">
          {index === ESCROW_CODE_LENGTH / 2 && (
            <span aria-hidden className="px-0.5 text-body-md text-grey-600">
              -
            </span>
          )}
          <input
            ref={(element) => {
              boxes.current[index] = element;
            }}
            aria-label={`Character ${index + 1}`}
            inputMode="text"
            autoCapitalize="characters"
            autoComplete={index === 0 ? "one-time-code" : "off"}
            maxLength={1}
            disabled={disabled}
            value={char}
            onChange={(event) => handleInput(index, event.target.value)}
            onKeyDown={(event) => handleKey(index, event)}
            onPaste={handlePaste}
            className={cn(
              "h-12 w-10 min-w-0 flex-1 rounded-lg border text-center text-body-md font-medium text-grey-900 outline-none transition-colors",
              "focus:border-primary-400 focus:ring-2 focus:ring-primary-100",
              char ? "border-primary-400 bg-white" : "border-grey-400 bg-grey-200/60",
            )}
          />
        </span>
      ))}
    </div>
  );
}

"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * A centred dialog on <dialog>, so focus trapping and Escape come free.
 *
 * Duplicates components/ui/Modal.tsx from the guarantor branch, which main
 * does not have yet. Kept here so this branch adds no shared files; replace
 * with the shared Modal once that branch merges.
 */
export function WorkerDialog({
  open,
  onClose,
  label,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  /** Accessible name, for dialogs whose heading is part of the content. */
  label: string;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-label={label}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      // A click on the dialog element itself is a click on the backdrop.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      className={cn(
        "m-auto max-h-[90dvh] overflow-y-auto w-[min(26rem,calc(100vw-2rem))] rounded-xl bg-white p-6 text-grey-900 shadow-3",
        "backdrop:bg-navy-500/40",
        className,
      )}
    >
      {children}
    </dialog>
  );
}

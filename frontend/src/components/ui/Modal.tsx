"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type ModalProps = {
  open: boolean;
  /** Called on Escape, backdrop click, or the close control. */
  onClose?: () => void;
  /** Accessible name for the dialog. */
  title: string;
  /** Hide the visible heading while keeping the accessible name. */
  hideTitle?: boolean;
  children: ReactNode;
  className?: string;
};

/** A centered dialog built on <dialog>, so focus and Escape come for free. */
export function Modal({ open, onClose, title, hideTitle, children, className }: ModalProps) {
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
      aria-label={hideTitle ? title : undefined}
      onCancel={(event) => {
        event.preventDefault();
        onClose?.();
      }}
      // A click landing on the dialog itself is a click on the backdrop:
      // anything inside sits in the content wrapper below.
      onClick={(event) => {
        if (event.target === ref.current) onClose?.();
      }}
      className={cn(
        "m-auto w-[min(26rem,calc(100vw-2rem))] rounded-xl bg-white p-6 text-grey-900 shadow-3",
        "backdrop:bg-navy-500/40",
        className,
      )}
    >
      <div className="flex flex-col items-center gap-4 text-center">
        {!hideTitle && <h2 className="text-h3 text-grey-900">{title}</h2>}
        {children}
      </div>
    </dialog>
  );
}

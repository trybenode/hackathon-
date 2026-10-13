"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";
import { LINKS } from "./links";

const CHOICES = [
  { href: LINKS.workerSignUp, label: "For worker" },
  { href: LINKS.developerSignUp, label: "For platform" },
];

/** "Get Started", opening a menu to choose the worker or platform sign-up. */
export function GetStartedMenu() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLAnchorElement | null>>([]);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    // Escape closes it wherever focus is, including on the button after a click.
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function openAt(index: number) {
    setOpen(true);
    // The items exist once the menu has rendered.
    requestAnimationFrame(() => itemRefs.current[index]?.focus());
  }

  function onTriggerKeyDown(event: KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      openAt(0);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      openAt(CHOICES.length - 1);
    }
  }

  function onMenuKeyDown(event: KeyboardEvent) {
    const current = itemRefs.current.indexOf(document.activeElement as HTMLAnchorElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      itemRefs.current[(current + step + CHOICES.length) % CHOICES.length]?.focus();
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={onTriggerKeyDown}
        className={cn(
          "inline-flex h-10 items-center justify-center rounded-md bg-primary-500 px-5 text-body-sm font-medium whitespace-nowrap text-white transition-colors hover:bg-primary-400",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 focus-visible:ring-offset-2",
        )}
      >
        Get Started
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Get started as"
          onKeyDown={onMenuKeyDown}
          className="absolute top-full right-0 z-20 mt-2 flex w-60 flex-col rounded-lg bg-white p-1.5 shadow-3"
        >
          {CHOICES.map((choice, index) => (
            <Link
              key={choice.href}
              ref={(node) => {
                itemRefs.current[index] = node;
              }}
              href={choice.href}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="rounded-md px-3 py-2.5 text-body-md text-grey-900 hover:bg-grey-50 focus:bg-grey-50 focus:outline-none"
            >
              {choice.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

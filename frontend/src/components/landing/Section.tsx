import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** The landing page's content width. */
export const CONTAINER = "mx-auto w-full max-w-[1232px] px-4 sm:px-6";

/** The small cyan label above a section heading ("THE PROBLEM"). */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("text-xs font-medium tracking-wide text-primary-500 uppercase", className)}>
      {children}
    </p>
  );
}

export function SectionHeading({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cn("text-h2 font-semibold text-grey-900 lg:text-[32px] lg:leading-10", className)}>{children}</h2>;
}

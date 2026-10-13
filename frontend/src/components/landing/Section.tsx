import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** The landing page's content width. */
export const CONTAINER = "mx-auto w-full max-w-[1232px] px-4 sm:px-6";

/** The deep blue of the footer and the step numbers. Read off the design;
 *  it isn't in the style guide. */
export const DEEP_BLUE = "bg-[#0a84b3]";

/** The pale cyan behind How it works and Who it's for, edge to edge. */
export const TINTED = "bg-primary-50/40";

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

import Link from "next/link";
import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

const variants = {
  fill: "bg-primary-500 text-white hover:bg-primary-400",
  outline: "border border-navy-500 bg-white text-grey-900 hover:bg-grey-50",
  // On the call-to-action banner's blue.
  light: "bg-primary-400 text-white hover:bg-primary-300",
  text: "text-white hover:underline",
};

/** A link styled as the landing page's buttons. */
export function LinkButton({
  variant = "fill",
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: keyof typeof variants }) {
  return (
    <Link
      className={cn(
        "inline-flex h-11 items-center justify-center gap-2 rounded-md px-6 text-body-sm font-medium whitespace-nowrap transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 focus-visible:ring-offset-2",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

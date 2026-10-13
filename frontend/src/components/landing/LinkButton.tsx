import Link from "next/link";
import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

const variants = {
  fill: "bg-primary-500 text-white hover:bg-primary-400",
  outline: "border border-primary-400 bg-white text-primary-500 hover:bg-primary-25",
  // On the call-to-action banner's blue.
  light: "bg-primary-400 text-white hover:bg-primary-300",
  text: "text-white hover:underline",
};

const sizes = { md: "h-11 px-6", sm: "h-10 px-5" };

/** A link styled as the landing page's buttons. */
export function LinkButton({
  variant = "fill",
  size = "md",
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: keyof typeof variants; size?: keyof typeof sizes }) {
  return (
    <Link
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md text-body-sm font-medium whitespace-nowrap transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 focus-visible:ring-offset-2",
        variants[variant],
        // A text link lines up with the text around it, so it has no padding.
        variant === "text" ? "h-11" : sizes[size],
        className,
      )}
      {...props}
    />
  );
}

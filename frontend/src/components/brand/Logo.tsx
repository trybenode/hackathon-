import { cn } from "@/lib/cn";
import { BRAND_NAME } from "@/lib/brand";

/**
 * The wordmark. A styled stand-in for the Figma's script logo until the
 * final name and logo arrive; swap the inside for the exported SVG then.
 */
export function Logo({ tone = "dark", className }: { tone?: "dark" | "light"; className?: string }) {
  return (
    <span
      className={cn(
        "font-serif text-h3 font-bold tracking-tight italic",
        tone === "dark" ? "text-grey-900" : "text-white",
        className,
      )}
    >
      {BRAND_NAME}
    </span>
  );
}

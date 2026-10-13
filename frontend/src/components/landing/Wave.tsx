import { cn } from "@/lib/cn";

/**
 * The soft light-blue curve between the hero and the problem band. A drawn
 * stand-in for the Figma's wave until it is exported.
 */
export function Wave({ flip = false, className }: { flip?: boolean; className?: string }) {
  return (
    <svg
      viewBox="0 0 1440 96"
      preserveAspectRatio="none"
      aria-hidden
      className={cn("block h-12 w-full text-primary-50 lg:h-24", flip && "rotate-180", className)}
    >
      <path fill="currentColor" d="M0 64C240 8 480 0 720 32s480 64 720 16v48H0z" />
    </svg>
  );
}

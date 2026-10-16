import Image from "next/image";
import { cn } from "@/lib/cn";
import { BRAND_NAME } from "@/lib/brand";

/**
 * The trybetrust wordmark. "light" swaps its black lettering for white, for
 * dark backgrounds; the cyan badge is the same in both. Size it by height.
 */
export function Logo({ tone = "dark", className }: { tone?: "dark" | "light"; className?: string }) {
  return (
    <Image
      src={tone === "dark" ? "/brand/logo.png" : "/brand/logo-light.png"}
      alt={BRAND_NAME}
      width={453}
      height={135}
      // Served as-is: Vercel Services doesn't route /_next/image.
      unoptimized
      className={cn("h-9 w-auto", className)}
    />
  );
}

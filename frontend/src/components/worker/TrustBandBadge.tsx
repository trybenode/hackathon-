import { Badge, type BadgeTone } from "@/components/ui";
import type { TrustBand } from "@/lib/workerRecord";

const BAND_TONE: Record<TrustBand, BadgeTone> = {
  High: "high",
  Medium: "medium",
  Low: "low",
  "Building History": "building",
};

/** The band score_worker() places a worker in, as a pill. */
export function TrustBandBadge({ band }: { band: TrustBand }) {
  return (
    <Badge
      tone={BAND_TONE[band]}
      // The designs mark the band with a small diamond rather than a dot.
      icon={<span aria-hidden className="h-1.5 w-1.5 rotate-45 bg-current" />}
      className="gap-2 px-3 py-1 text-body-sm font-normal"
    >
      {band}
    </Badge>
  );
}

import { Badge, type BadgeTone } from "@/components/ui";
import type { TrustBand } from "@/lib/workerRecordMock";

const BAND_TONE: Record<TrustBand, BadgeTone> = {
  High: "high",
  Medium: "medium",
  Low: "low",
  "Building History": "building",
};

/** The band score_worker() places a worker in, as a pill. */
export function TrustBandBadge({ band }: { band: TrustBand }) {
  return (
    <Badge tone={BAND_TONE[band]} dot className="text-body-sm font-normal">
      {band}
    </Badge>
  );
}

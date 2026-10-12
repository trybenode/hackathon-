"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { LivenessCapture } from "@/components/verification/LivenessCapture";
import { getInstrument, submitLiveness } from "@/lib/guarantor";

export function LivenessCheck({ instrumentId }: { instrumentId: string }) {
  const router = useRouter();
  const [verified, setVerified] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);

  // Send the guarantor back if the instrument is not awaiting verification.
  useEffect(() => {
    let cancelled = false;

    async function guard() {
      try {
        const instrument = await getInstrument(instrumentId);
        if (cancelled) return;
        if (instrument.status === "Pending Signature") {
          router.replace(`/guarantor/${instrumentId}/review`);
        } else if (instrument.status === "Active") {
          setVerified(true);
        } else if (instrument.status !== "Pending Verification") {
          setBlocked("This request is no longer awaiting verification.");
        }
      } catch {
        if (!cancelled) setBlocked("Could not load this request.");
      }
    }

    void guard();
    return () => {
      cancelled = true;
    };
  }, [instrumentId, router]);

  const submit = useCallback(
    async (frame: Blob) => {
      await submitLiveness(instrumentId, frame);
    },
    [instrumentId],
  );

  return (
    <LivenessCapture
      submit={submit}
      alreadyVerified={verified}
      blocked={blocked}
      onDone={() => router.push("/dashboard")}
    />
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { LivenessCapture } from "@/components/verification/LivenessCapture";
import { useOnboarding } from "@/components/verification/useOnboarding";
import { submitWorkerLiveness } from "@/lib/onboarding";

/** The worker's liveness check; once it passes they move on to their guarantor. */
export function WorkerLiveness() {
  const router = useRouter();
  const { error } = useOnboarding("liveness");

  const submit = useCallback(async (frame: Blob) => {
    await submitWorkerLiveness(frame);
  }, []);

  return <LivenessCapture submit={submit} blocked={error} onDone={() => router.push("/join/guarantor")} />;
}

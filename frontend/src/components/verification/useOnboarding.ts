"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/guarantor";
import { getOnboarding, type Onboarding, type OnboardingStep } from "@/lib/onboarding";

const ORDER: OnboardingStep[] = ["identity", "liveness", "guarantor"];

/** Where a worker goes for a step, or Home once nothing is left. */
export function stepPath(step: OnboardingStep | null) {
  return step ? `/join/${step}` : "/worker";
}

/**
 * Loads the worker's onboarding and keeps them on the right screen: signed-out
 * visitors go to sign-up, and anyone ahead of or behind `step` is moved to the
 * step they are actually on. The guarantor step stays reachable once both
 * checks pass, so a worker can come back to it from Home.
 */
export function useOnboarding(step: OnboardingStep) {
  const router = useRouter();
  const [data, setData] = useState<Onboarding | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getOnboarding()
      .then((loaded) => {
        if (cancelled) return;
        const here = ORDER.indexOf(step);
        const unfinished = loaded.next_step ? ORDER.indexOf(loaded.next_step) : ORDER.length;
        // Behind: an earlier step is still open. Ahead: this check already passed.
        const done = step === "identity" ? loaded.identity_verified : step === "liveness" && loaded.liveness_verified;
        if (unfinished < here || done) {
          router.replace(stepPath(loaded.next_step));
          return;
        }
        setData(loaded);
      })
      .catch((cause) => {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          router.replace("/join/sign-in");
          return;
        }
        setError(
          cause instanceof ApiError && cause.status === 404
            ? "This account has no worker profile."
            : "Could not load your verification. Try again.",
        );
      });

    return () => {
      cancelled = true;
    };
  }, [router, step]);

  return { data, error };
}

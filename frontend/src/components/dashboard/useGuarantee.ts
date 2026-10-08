"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getGuarantee, type GuaranteeDetail } from "@/lib/guarantor";

/**
 * Loads one of the signed-in guarantor's guarantees, sending them to sign in
 * when the session has expired.
 */
export function useGuarantee(instrumentId: string) {
  const router = useRouter();
  const [data, setData] = useState<GuaranteeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const loaded = await getGuarantee(instrumentId);
        if (!cancelled) setData(loaded);
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          router.replace("/sign-in");
          return;
        }
        setError(
          cause instanceof ApiError && cause.status === 404
            ? "We could not find that guarantee."
            : "Could not load this guarantee.",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [instrumentId, router]);

  return { data, error, loading };
}

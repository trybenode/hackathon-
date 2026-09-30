"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getDashboard, type DashboardData } from "@/lib/guarantor";

/**
 * Loads the signed-in guarantor's dashboard, sending them to sign in when the
 * session has expired.
 */
export function useDashboard() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const loaded = await getDashboard();
        if (!cancelled) setData(loaded);
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          router.replace("/sign-in");
          return;
        }
        setError("Could not load your dashboard.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return { data, error, loading };
}

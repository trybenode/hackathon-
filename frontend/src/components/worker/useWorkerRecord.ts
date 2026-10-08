"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/guarantor";
import { getWorkerRecord, type WorkerRecord } from "@/lib/workerRecord";

/**
 * Loads the signed-in worker's record, sending them to sign in (and back here
 * afterwards) when there is no session.
 */
export function useWorkerRecord() {
  const router = useRouter();
  const pathname = usePathname();
  const [data, setData] = useState<WorkerRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const loaded = await getWorkerRecord();
        if (!cancelled) setData(loaded);
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
          return;
        }
        setError(
          cause instanceof ApiError && cause.status === 404
            ? "This account has no worker profile."
            : "Could not load your record.",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  return { data, error, loading };
}

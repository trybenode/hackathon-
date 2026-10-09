"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiFailure, errorMessage } from "@/lib/portability";
import { getWorkerRecord, type WorkerRecord } from "@/lib/workerRecord";

/** Canonical record loader; cancel stale requests and retain data on refresh. */
export function useWorkerRecord() {
  const router = useRouter();
  const pathname = usePathname();
  const [data, setData] = useState<WorkerRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const request = useRef<AbortController | null>(null);
  const load = useCallback(
    (controller: AbortController) =>
      getWorkerRecord(controller.signal)
        .then((result) => {
          if (!controller.signal.aborted) {
            setData(result);
            setError(null);
          }
        })
        .catch((cause) => {
          if (controller.signal.aborted) return;
          if (cause instanceof ApiFailure && cause.status === 401)
            router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
          setError(errorMessage(cause));
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        }),
    [pathname, router],
  );
  const refresh = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError(null);
    return load(controller);
  }, [load]);
  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    void load(controller);
    return () => request.current?.abort();
  }, [load]);
  return { data, error, loading, refresh, retry: refresh };
}

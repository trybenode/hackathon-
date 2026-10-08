"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/guarantor";

/**
 * Loads something only a signed-in worker may see, sending them to sign in
 * (and back here afterwards) when there is no session. `reload` fetches it
 * again, e.g. after an action changed it. Pass `load` through useCallback so
 * it only changes when what it fetches does.
 */
export function useWorkerResource<T>(load: () => Promise<T>, notFound: string) {
  const router = useRouter();
  const pathname = usePathname();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);

  const reload = useCallback(() => setVersion((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        const loaded = await load();
        if (!cancelled) {
          setData(loaded);
          setError(null);
        }
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
          return;
        }
        setError(cause instanceof ApiError && cause.status === 404 ? notFound : "Could not load this.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [load, version, pathname, router, notFound]);

  return { data, error, loading, reload };
}

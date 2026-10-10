"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getDeveloperDashboard, type DeveloperDashboard } from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

/**
 * Loads the signed-in developer's dashboard. Signed-out visitors go to sign
 * in and come back here afterwards.
 */
export function useDeveloper() {
  const router = useRouter();
  const pathname = usePathname();
  const [data, setData] = useState<DeveloperDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getDeveloperDashboard()
      .then((loaded) => {
        if (!cancelled) setData(loaded);
      })
      .catch((cause) => {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
          return;
        }
        setError(
          cause instanceof ApiError && cause.status === 404
            ? "This account has no developer profile."
            : "Could not load your dashboard. Try again.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, router, version]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  return { data, error, reload, setData };
}

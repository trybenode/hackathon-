"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getDeveloperDashboard, type DeveloperDashboard } from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

type DeveloperState = {
  data: DeveloperDashboard | null;
  error: string | null;
  /** Fetch the dashboard again, e.g. after a step changes it. */
  reload: () => void;
};

const DeveloperContext = createContext<DeveloperState | null>(null);

/**
 * Loads the signed-in developer's dashboard once for every developer page and
 * the sidebar. Signed-out visitors go to sign in and come back afterwards.
 */
export function DeveloperProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [data, setData] = useState<DeveloperDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getDeveloperDashboard()
      .then((loaded) => {
        if (!cancelled) {
          setData(loaded);
          setError(null);
        }
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
    // The pathname is read only for the sign-in return; navigating between
    // developer pages should not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, version]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  return <DeveloperContext.Provider value={{ data, error, reload }}>{children}</DeveloperContext.Provider>;
}

export function useDeveloper(): DeveloperState {
  const state = useContext(DeveloperContext);
  if (!state) throw new Error("useDeveloper must be used inside DeveloperProvider");
  return state;
}

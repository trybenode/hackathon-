"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { OutcomeList } from "@/components/worker/OutcomeList";
import { RecordGate } from "@/components/worker/RecordGate";
import { Button } from "@/components/ui";
import { ApiFailure, errorMessage } from "@/lib/portability";
import { getRecordOutcomes, type RecordOutcome } from "@/lib/workerRecord";

/** Every verified outcome on the worker's record, newest first, 20 at a time. */
export function OutcomeHistory() {
  const router = useRouter();
  const pathname = usePathname();
  const [outcomes, setOutcomes] = useState<RecordOutcome[] | null>(null);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((result: Awaited<ReturnType<typeof getRecordOutcomes>>) => {
    setOutcomes((current) => (result.page === 1 || !current ? result.items : [...current, ...result.items]));
    setPage(result.page);
    setPages(result.pages);
    setTotal(result.total);
    setError(null);
  }, []);

  const fail = useCallback(
    (cause: unknown) => {
      if (cause instanceof ApiFailure && cause.status === 401) {
        router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
        return;
      }
      setError(errorMessage(cause));
    },
    [pathname, router],
  );

  const load = useCallback((next: number) => getRecordOutcomes(next).then(apply).catch(fail), [apply, fail]);

  useEffect(() => {
    let cancelled = false;
    getRecordOutcomes(1)
      .then((result) => {
        if (!cancelled) apply(result);
      })
      .catch((cause) => {
        if (!cancelled) fail(cause);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apply, fail]);

  async function more() {
    setLoadingMore(true);
    await load(page + 1);
    setLoadingMore(false);
  }

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Verified Outcomes</h1>
      </header>

      <RecordGate loading={loading} error={error} hasData={outcomes !== null} onRetry={() => load(1)}>
        {outcomes && (
          <div className="flex flex-col gap-4 px-6 pt-4 pb-4">
            <OutcomeList outcomes={outcomes} />
            {page < pages && (
              <Button variant="outline" className="self-center rounded-xl px-8" disabled={loadingMore} onClick={more}>
                {loadingMore ? "Loading…" : `Show more (${total - outcomes.length} left)`}
              </Button>
            )}
          </div>
        )}
      </RecordGate>
    </main>
  );
}

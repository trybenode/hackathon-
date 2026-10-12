"use client";
/** Combines localized evidence history with detailed verified outcomes for the record page. */
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { OutcomeList } from "@/components/worker/OutcomeList";
import { RecordGate } from "@/components/worker/RecordGate";
import { ApiFailure, errorMessage, type HistoryItem, type Page } from "@/lib/portability";
import { historyDate } from "@/lib/history";
import { getWorkerHistory, getRecordOutcomes, type RecordOutcome } from "@/lib/workerRecord";

export function OutcomeHistory() {
  const { w } = useWorkerCopy();
  const router = useRouter();
  const [view, setView] = useState<"verified" | "history">("verified");
  return <main className="flex flex-col">
    <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
      <button type="button" aria-label={w("Back")} onClick={() => router.back()}><ArrowLeftIcon /></button>
      <h1 className="text-body-lg font-semibold">{w("Work history")}</h1>
    </header>
    <nav aria-label={w("Work history")} className="flex flex-wrap gap-2 px-6 pt-4">
      <Button variant="outline" aria-pressed={view === "verified"} onClick={() => setView("verified")}>{w("Verified outcomes")}</Button>
      <Button variant="outline" aria-pressed={view === "history"} onClick={() => setView("history")}>{w("Work history")}</Button>
    </nav>
    {view === "verified" ? <VerifiedOutcomeHistory /> : <WorkHistory />}
  </main>;
}

/** Every verified outcome on the worker's record, newest first, 20 at a time. */
function VerifiedOutcomeHistory() {
  const { w } = useWorkerCopy();
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
    const controller = new AbortController();
    getRecordOutcomes(1, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) apply(result);
      })
      .catch((cause) => {
        if (!controller.signal.aborted) fail(cause);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
    };
  }, [apply, fail]);

  async function more() {
    setLoadingMore(true);
    await load(page + 1);
    setLoadingMore(false);
  }

  return (
    <section className="flex flex-col">

      <RecordGate loading={loading} error={error} hasData={outcomes !== null} onRetry={() => load(outcomes === null ? 1 : page + 1)}>
        {outcomes && (
          <div className="flex flex-col gap-4 px-6 pt-4 pb-4">
            <OutcomeList outcomes={outcomes} />
            {page < pages && (
              <Button variant="outline" className="self-center rounded-xl px-8" disabled={loadingMore} onClick={more}>
                {loadingMore ? w("Loading…") : `${w("Show more")} (${total - outcomes.length})`}
              </Button>
            )}
          </div>
        )}
      </RecordGate>
    </section>
  );
}

function WorkHistory() {
  const { w, language } = useWorkerCopy();

  const router = useRouter();
  const pathname = usePathname();
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<Page<HistoryItem> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const retry = useCallback(() => {
    setLoading(true);
    setRevision((value) => value + 1);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    getWorkerHistory(page, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) {
          setData(value);
          setError("");
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          if (e instanceof ApiFailure && e.status === 401) {
            router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
            return;
          }
          setError(errorMessage(e));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [page, revision, pathname, router]);
  function changePage(next: number) {
    setLoading(true);
    setError("");
    setPage(next);
  }
  return (
    <section className="flex flex-col gap-5 p-6">
      <p className="text-body-sm text-grey-600">
        {w("Verified evidence and self-declared history are labelled separately. Recording work does not establish customer confirmation.")}</p>
      {loading && <p role="status">{w("Loading history…")}</p>}
      {error && (
        <div role="alert">
          <p>{w(error)}</p>
          <Button variant="outline" onClick={retry}>
            {w("Retry history")}</Button>
        </div>
      )}
      {!loading && !error && data && (
        <>
          <p className="text-body-sm">{data.total} {w("records")}</p>
          {!data.total && <p>{w("No work history yet.")}</p>}
          <ul className="space-y-3">
            {data.items.map((item) => (
              <li
                key={item.outcome_id}
                className="rounded-xl border border-stroke p-4"
              >
                <p className="font-semibold">
                  {item.verified
                    ? w("Verified evidence")
                    : w("Self-declared history")}
                </p>
                <p className="mt-2 text-body-sm">
                  {w(item.status.replace("_", " "))} ·{" "}
                  {historyDate(item.occurred_at, language)}
                </p>
                <p className="text-body-sm">{w(item.completion_status)}</p>
                <p className="mt-2 text-body-sm text-grey-600">
                  {w("Source:")}{item.source_name ?? item.source_platform} ·{" "}
                  {item.verification_method?.replaceAll("_", " ") ??
                    w("Verification method not recorded")}
                </p>
                <p className="text-body-sm">
                  {w("Rating:")}{" "}
                  {item.rating === null ? w("Not recorded") : `${item.rating}/5`}
                </p>
                {item.verified_at && (
                  <p className="text-body-sm">
                    {w("Verified")}{historyDate(item.verified_at, language)}
                  </p>
                )}
              </li>
            ))}
          </ul>
          {data.pages > 1 && (
            <nav
              aria-label={w("History pages")}
              className="flex items-center justify-between gap-2"
            >
              <Button
                variant="outline"
                disabled={page === 1}
                onClick={() => changePage(page - 1)}
              >
                {w("Previous")}</Button>
              <span>
                {page} / {data.pages}
              </span>
              <Button
                variant="outline"
                disabled={page >= data.pages}
                onClick={() => changePage(page + 1)}
              >
                {w("Next")}</Button>
            </nav>
          )}
        </>
      )}
    </section>
  );
}

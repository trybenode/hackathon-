"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { ArrowLeftIcon } from "@/components/worker/icons";
import {
  errorMessage,
  type HistoryItem,
  type Page,
} from "@/lib/portability";
import { historyDate } from "@/lib/history";
import { getWorkerHistory } from "@/lib/workerRecord";

export function OutcomeHistory() {
  const { w, language } = useWorkerCopy();

  const router = useRouter();
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<Page<HistoryItem> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const retry = useCallback(() => setRevision((value) => value + 1), []);
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
        if (!controller.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [page, revision]);
  function changePage(next: number) {
    setLoading(true);
    setError("");
    setPage(next);
  }
  return (
    <main className="flex flex-col gap-5 p-6">
      <header className="flex items-center gap-3">
        <button aria-label={w("Back")} onClick={() => router.back()}>
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold">{w("Work history")}</h1>
      </header>
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
    </main>
  );
}

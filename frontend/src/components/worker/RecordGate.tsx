"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";
import type { ReactNode } from "react";

/** Shows loading or the error until the worker's record has arrived. */
export function RecordGate({
  loading,
  error,
  children,
  onRetry,
  hasData = false,
}: {
  loading: boolean;
  error: string | null;
  children: ReactNode;
  onRetry?: () => void;
  hasData?: boolean;
}) {
  const { w } = useWorkerCopy();

  if (loading && !hasData) {
    return (
      <p role="status" className="px-6 pt-8 text-body-sm text-grey-600">
        {w("Loading…")}</p>
    );
  }
  if (error && !hasData) {
    return (
      <div className="px-6 pt-8">
        <p role="alert" className="text-body-sm text-error">
          {w(error)}
        </p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 min-h-11 rounded-lg border border-stroke px-4"
          >
            {w("Retry record")}</button>
        )}
      </div>
    );
  }
  return (
    <>
      {loading && (
        <p role="status" className="px-6 pt-3 text-body-sm">
          {w("Refreshing current evidence…")}</p>
      )}
      {error && (
        <div role="alert" className="px-6 pt-3 text-body-sm text-error">
          {w("Current evidence could not be refreshed:")}{w(error)}.{" "}
          {onRetry && (
            <button className="min-h-11 underline" onClick={onRetry}>
              {w("Retry")}</button>
          )}
        </div>
      )}
      {children}
    </>
  );
}

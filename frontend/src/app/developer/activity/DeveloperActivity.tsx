"use client";

import { useEffect, useState } from "react";
import { useDeveloper } from "@/components/developer/DeveloperContext";
import { ActivityIcon } from "@/components/developer/icons";
import { PageHeader } from "@/components/developer/PageHeader";
import { Button, Select } from "@/components/ui";
import { cn } from "@/lib/cn";
import { getCallLog, maskKeyId, type LogEntry, type LogOutcome, type LogPage } from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

const OUTCOMES: { value: LogOutcome; label: string }[] = [
  { value: "all", label: "All" },
  { value: "success", label: "Successful" },
  { value: "error", label: "Errors" },
];

function when(at: string) {
  return new Date(at).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function route(path: string) {
  return path.replace(/^\/api\/v1/, "");
}

function Status({ code }: { code: number }) {
  const ok = code >= 200 && code < 300;
  return (
    <span
      className={cn(
        "rounded-md px-2 py-0.5 font-mono text-xs",
        ok ? "bg-success-light text-grey-900" : code >= 500 ? "bg-error-light text-error" : "bg-warning-light text-grey-900",
      )}
    >
      {code}
    </span>
  );
}

function KeyCell({ entry }: { entry: LogEntry }) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className="truncate text-body-sm text-grey-900">
        {entry.key.name}
        {entry.key.revoked && <span className="text-grey-600"> · revoked</span>}
      </span>
      <span className="truncate font-mono text-xs text-grey-600">
        {entry.key.key_id ? maskKeyId(entry.key.key_id) : entry.key.environment}
      </span>
    </span>
  );
}

/** "Activity": every call made with the platform's keys, to debug an integration. */
export function DeveloperActivity() {
  const { data: account } = useDeveloper();
  const approved = account?.kyb_status === "approved";
  const [page, setPage] = useState(1);
  const [key, setKey] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<LogOutcome>("all");
  const [log, setLog] = useState<LogPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!approved) return;
    let cancelled = false;
    getCallLog({ page, key, outcome })
      .then((loaded) => {
        if (!cancelled) {
          setLog(loaded);
          setError(null);
        }
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof ApiError ? cause.message : "Could not load activity.");
      });
    return () => {
      cancelled = true;
    };
  }, [approved, page, key, outcome]);

  const keyOptions = [
    { value: "all", label: "All keys" },
    ...(log?.keys ?? []).map((item) => ({
      value: item.id,
      label: `${item.name} · ${item.environment}${item.revoked ? " · revoked" : ""}`,
    })),
  ];

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Activity"
        description="Every call made with your API keys. Method, route, status and duration only: no request bodies or worker ids."
      />

      {account && !approved && (
        <p className="rounded-xl border border-stroke px-6 py-12 text-center text-body-sm text-grey-600">
          Activity appears once your business is verified and you start calling the API.
        </p>
      )}

      {approved && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div className="w-full sm:w-72">
              <Select
                label="Key"
                options={keyOptions}
                value={key ?? "all"}
                onChange={(value) => {
                  setKey(value && value !== "all" ? value : null);
                  setPage(1);
                }}
              />
            </div>
            <div role="group" aria-label="Status" className="flex rounded-lg border border-stroke p-1">
              {OUTCOMES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={outcome === option.value}
                  onClick={() => {
                    setOutcome(option.value);
                    setPage(1);
                  }}
                  className={cn(
                    "rounded-md px-4 py-1.5 text-body-sm",
                    outcome === option.value ? "bg-primary-50 font-medium text-grey-900" : "text-grey-600 hover:text-grey-900",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <p role="alert" className="text-body-sm text-error">
              {error}
            </p>
          )}

          {log && log.items.length === 0 && (
            <div className="flex flex-col items-center gap-2 rounded-xl border border-stroke px-6 py-12 text-center">
              <ActivityIcon className="text-grey-600" width={28} height={28} />
              <p className="text-body-md text-grey-900">No calls to show</p>
              <p className="text-body-sm text-grey-600">
                {key || outcome !== "all"
                  ? "Nothing matches these filters."
                  : "Calls made with your API keys appear here as they happen."}
              </p>
            </div>
          )}

          {log && log.items.length > 0 && (
            <>
              <div className="hidden overflow-hidden rounded-xl border border-stroke md:block">
                <table className="w-full table-fixed text-left">
                  <thead className="bg-grey-50 text-xs text-grey-600">
                    <tr>
                      <th className="w-[18%] px-4 py-3 font-medium">Time</th>
                      <th className="w-[24%] px-4 py-3 font-medium">Key</th>
                      <th className="w-[38%] px-4 py-3 font-medium">Request</th>
                      <th className="w-[10%] px-4 py-3 font-medium">Status</th>
                      <th className="w-[10%] px-4 py-3 text-right font-medium">Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {log.items.map((entry, index) => (
                      <tr key={`${entry.at}-${index}`} className="border-t border-stroke">
                        <td className="px-4 py-3 text-body-sm whitespace-nowrap text-grey-900">{when(entry.at)}</td>
                        <td className="px-4 py-3">
                          <KeyCell entry={entry} />
                        </td>
                        <td className="truncate px-4 py-3 font-mono text-xs text-grey-900">
                          <span className="font-semibold">{entry.method}</span> {route(entry.path)}
                        </td>
                        <td className="px-4 py-3">
                          <Status code={entry.status_code} />
                        </td>
                        <td className="px-4 py-3 text-right text-body-sm text-grey-900">{entry.duration_ms} ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <ul className="flex flex-col gap-3 md:hidden">
                {log.items.map((entry, index) => (
                  <li key={`${entry.at}-${index}`} className="flex flex-col gap-2 rounded-xl border border-stroke p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs text-grey-600">{when(entry.at)}</span>
                      <Status code={entry.status_code} />
                    </div>
                    <p className="font-mono text-xs break-all text-grey-900">
                      <span className="font-semibold">{entry.method}</span> {route(entry.path)}
                    </p>
                    <div className="flex items-end justify-between gap-3">
                      <KeyCell entry={entry} />
                      <span className="shrink-0 text-xs text-grey-600">{entry.duration_ms} ms</span>
                    </div>
                  </li>
                ))}
              </ul>

              <div className="flex items-center justify-between gap-3 pt-2">
                <span className="text-body-sm text-grey-600">
                  {log.total} {log.total === 1 ? "call" : "calls"} · page {log.page} of {log.pages}
                </span>
                <div className="flex gap-2">
                  <Button variant="outline" className="rounded-lg px-4" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    className="rounded-lg px-4"
                    disabled={page >= log.pages}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

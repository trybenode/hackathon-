"use client";

import { useState } from "react";
import { GuaranteeCard } from "@/components/dashboard/GuaranteeCard";
import { cn } from "@/lib/cn";
import { useDashboard } from "../useDashboard";

const TABS = ["All", "Active", "Completed"] as const;
type Tab = (typeof TABS)[number];

/** The API decides which bucket a guarantee belongs to; tabs just filter. */
const TAB_BUCKET: Record<Exclude<Tab, "All">, string> = {
  Active: "active",
  Completed: "completed",
};

export function GuaranteeList() {
  const { data, error, loading } = useDashboard();
  const [tab, setTab] = useState<Tab>("All");

  const guarantees = data?.guarantees ?? [];
  const shown =
    tab === "All" ? guarantees : guarantees.filter((item) => item.bucket === TAB_BUCKET[tab]);

  return (
    <main className="flex flex-col">
      <header className="border-b border-stroke px-6 pt-8 pb-5">
        <h1 className="text-body-lg font-semibold text-grey-900">My guarantees</h1>
      </header>

      <div
        role="tablist"
        aria-label="Filter guarantees"
        className="flex border-b border-stroke px-6 pt-4"
      >
        {TABS.map((name) => {
          const selected = tab === name;
          return (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setTab(name)}
              className={cn(
                "flex-1 border-b-2 px-2 pb-3 text-body-md transition-colors",
                selected
                  ? "border-primary-500 bg-primary-25 font-medium text-grey-900"
                  : "border-transparent text-grey-400",
              )}
            >
              {name}
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-4 px-6 pt-6">
        {loading && (
          <p role="status" className="text-body-sm text-grey-600">
            Loading…
          </p>
        )}
        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}
        {!loading && !error && shown.length === 0 && (
          <p className="text-body-sm text-grey-600">Nothing here yet.</p>
        )}
        {shown.map((guarantee) => (
          <GuaranteeCard key={guarantee.instrument_id} guarantee={guarantee} layout="inline" />
        ))}
      </div>
    </main>
  );
}

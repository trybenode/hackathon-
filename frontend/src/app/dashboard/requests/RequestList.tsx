"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { RequestCard } from "@/components/dashboard/RequestCard";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { cn } from "@/lib/cn";
import type { GuaranteeCard } from "@/lib/guarantor";
import { useDashboard } from "../useDashboard";

const TABS = ["Pending", "Accepted", "Declined"] as const;
type Tab = (typeof TABS)[number];

const TAB_BUCKET: Record<Tab, GuaranteeCard["request_bucket"]> = {
  Pending: "pending",
  Accepted: "accepted",
  Declined: "declined",
};

/**
 * Requests a guarantor has been sent, by answer. "My guarantees" is the other
 * side: the guarantees those accepted requests became, for their year.
 */
export function RequestList() {
  const router = useRouter();
  const { data, error, loading } = useDashboard();
  const [tab, setTab] = useState<Tab>("Pending");

  const shown = (data?.guarantees ?? []).filter((item) => item.request_bucket === TAB_BUCKET[tab]);

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Guarantee Requests</h1>
      </header>

      <div role="tablist" aria-label="Filter requests" className="flex justify-center px-6 pt-8">
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
                "border-b-2 px-4 pt-1.5 pb-2 text-body-md transition-colors",
                selected
                  ? "border-primary-500 bg-primary-50 font-medium text-primary-500"
                  : "border-stroke text-grey-400",
              )}
            >
              {name}
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-8 px-6 pt-8">
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
        {shown.map((request) => (
          <RequestCard key={request.instrument_id} request={request} />
        ))}
      </div>
    </main>
  );
}

"use client";

import { useState } from "react";
import { GuaranteeCard } from "@/components/dashboard/GuaranteeCard";
import { CheckIcon, ChevronDownIcon, CloseIcon, WarningTriangleIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { formatActivityTime } from "@/lib/format";
import { useDashboard } from "./useDashboard";

export function HomeScreen() {
  const { data, error, loading } = useDashboard();
  const [bannerOpen, setBannerOpen] = useState(true);
  const [listOpen, setListOpen] = useState(true);

  if (loading) {
    return (
      <main className="px-6 pt-10">
        <p role="status" className="text-body-sm text-grey-600">
          Loading…
        </p>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="px-6 pt-10">
        <p role="alert" className="text-body-sm text-error">
          {error ?? "Could not load your dashboard."}
        </p>
      </main>
    );
  }

  const active = data.guarantees.filter((item) => item.status === "Active");
  const waiting = data.action_required;

  return (
    <main className="flex flex-col">
      <header className="flex flex-col gap-1 border-b border-stroke px-6 pt-8 pb-5">
        <h1 className="text-body-lg font-semibold text-grey-900">
          Good morning, {data.greeting_name}
        </h1>
        <p className="text-body-sm text-grey-600">Your guarantee overview</p>
      </header>

      <div className="flex flex-col gap-6 px-6 pt-6">
        {waiting && bannerOpen && (
          <section className="flex items-start gap-3 rounded-lg bg-warning p-4 text-white">
            <WarningTriangleIcon className="mt-0.5 shrink-0" width={22} height={22} />
            <div className="flex flex-1 flex-col gap-1">
              <p className="text-body-md font-semibold">Action required</p>
              <p className="text-body-sm text-white/90">
                {waiting.worker_name} requested you as a guarantor
                {waiting.job_title ? ` for a ${waiting.job_title.toLowerCase()} job` : ""}
              </p>
            </div>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => setBannerOpen(false)}
              className="shrink-0 rounded-sm text-white/90 hover:text-white"
            >
              <CloseIcon width={18} height={18} />
            </button>
          </section>
        )}

        <section className="grid grid-cols-2 gap-4">
          {[
            { label: "Active Guarantees", value: data.active_count },
            { label: "Completed Guarantees", value: data.completed_count },
          ].map((stat) => (
            <div
              key={stat.label}
              className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4 shadow-1"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-pill bg-info-light">
                <CheckIcon className="text-primary-500" width={18} height={18} />
              </span>
              <span className="flex flex-col gap-1">
                <span className="text-body-sm text-grey-600">{stat.label}</span>
                <span className="text-body-lg text-grey-900">{stat.value}</span>
              </span>
            </div>
          ))}
        </section>

        <section className="flex flex-col gap-4">
          <button
            type="button"
            onClick={() => setListOpen((open) => !open)}
            aria-expanded={listOpen}
            className="flex items-start justify-between gap-4 border-b border-stroke pb-4 text-left"
          >
            <span className="flex flex-col gap-1">
              <span className="text-body-md font-semibold text-grey-900">Active guarantees</span>
              <span className="text-body-sm text-grey-600">
                {active.length > 0
                  ? active.map((item) => `${item.worker_name} - ${item.job_title ?? ""}`).join(", ")
                  : "Nothing active right now"}
              </span>
            </span>
            <ChevronDownIcon
              className={cn(
                "mt-1 shrink-0 text-grey-900 transition-transform",
                listOpen && "rotate-180",
              )}
            />
          </button>

          {listOpen &&
            active.map((guarantee) => (
              <GuaranteeCard key={guarantee.instrument_id} guarantee={guarantee} />
            ))}
        </section>

        {data.recent_activity.length > 0 && (
          <section className="flex flex-col overflow-hidden rounded-lg border border-stroke">
            <h2 className="bg-primary-25 px-4 py-4 text-body-md font-medium text-grey-900">
              Recent activity
            </h2>
            <ul className="flex flex-col">
              {data.recent_activity.slice(0, 5).map((entry) => (
                <li
                  key={entry.id}
                  className="flex items-start gap-3 border-t border-stroke px-4 py-3 first:border-t-0"
                >
                  <CheckIcon className="mt-1 shrink-0 text-grey-900" />
                  <span className="flex flex-col gap-0.5">
                    <span className="text-body-sm font-medium text-grey-900">{entry.label}</span>
                    <span className="text-body-sm text-grey-600">
                      {formatActivityTime(entry.at)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </main>
  );
}

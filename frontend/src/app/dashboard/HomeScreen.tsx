"use client";

import Link from "next/link";
import { useState } from "react";
import { GuaranteeCard } from "@/components/dashboard/GuaranteeCard";
import { CheckIcon, ChevronDownIcon, ClockIcon, WarningTriangleIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { formatActivityTime } from "@/lib/format";
import { useDashboard } from "./useDashboard";

export function HomeScreen() {
  const { data, error, loading } = useDashboard();
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

  const active = data.guarantees.filter((item) => item.bucket === "active");
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
        {waiting && (
          <section className="flex items-center gap-3 rounded-lg bg-warning p-4 text-white">
            <WarningTriangleIcon className="shrink-0" width={22} height={22} />
            <div className="flex flex-1 flex-col gap-1">
              <p className="text-body-md font-semibold">Action required</p>
              <p className="text-body-sm text-white/90">
                {waiting.worker_name} requested you as a guarantor
              </p>
            </div>
            <Link
              href="/dashboard/requests"
              className="shrink-0 rounded-pill bg-black/30 px-5 py-2.5 text-body-md font-semibold text-white transition-colors hover:bg-black/40"
            >
              View
            </Link>
          </section>
        )}

        <section className="grid grid-cols-3 gap-3">
          {[
            {
              label: "Active Guarantees",
              value: data.active_count,
              ring: "bg-primary-50",
              fill: "bg-info",
              Icon: CheckIcon,
            },
            {
              label: "Pending Request",
              value: data.pending_count,
              ring: "bg-warning-light",
              fill: "bg-warning",
              Icon: ClockIcon,
            },
            {
              label: "Expired Guarantees",
              value: data.expired_count,
              ring: "bg-warning-light",
              fill: "bg-error-mid",
              Icon: ClockIcon,
            },
          ].map(({ label, value, ring, fill, Icon }) => (
            <div
              key={label}
              className="flex flex-col gap-3 rounded-xl border border-stroke bg-white p-3"
            >
              <span className={cn("flex h-10 w-10 items-center justify-center rounded-pill", ring)}>
                <span className={cn("flex h-6 w-6 items-center justify-center rounded-pill", fill)}>
                  <Icon className="text-white" width={14} height={14} />
                </span>
              </span>
              <span className="flex flex-col gap-1">
                <span className="text-body-sm text-grey-600">{label}</span>
                <span className="text-body-lg text-grey-900">{value}</span>
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
                  ? active
                      .map((item) =>
                        item.job_title ? `${item.worker_name} - ${item.job_title}` : item.worker_name,
                      )
                      .join(", ")
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
              <GuaranteeCard key={guarantee.instrument_id} guarantee={guarantee} variant="home" />
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
                    <span className="text-body-sm font-medium text-grey-900">
                      {entry.worker_name ? `${entry.label} - ${entry.worker_name}` : entry.label}
                    </span>
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

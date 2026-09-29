"use client";

import { useState } from "react";
import { GuaranteeCard } from "@/components/dashboard/GuaranteeCard";
import { CheckIcon, ChevronDownIcon, CloseIcon, WarningTriangleIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { actionRequired, guarantees, recentActivity, stats, guarantor } from "@/lib/dashboardMock";

export function HomeScreen() {
  const [bannerOpen, setBannerOpen] = useState(true);
  const [listOpen, setListOpen] = useState(true);
  const active = guarantees.filter((item) => item.status === "Active");

  return (
    <main className="flex flex-col">
      <header className="flex flex-col gap-1 border-b border-stroke px-6 pt-8 pb-5">
        <h1 className="text-body-lg font-semibold text-grey-900">
          Good morning, {guarantor.firstName}
        </h1>
        <p className="text-body-sm text-grey-600">Your guarantee overview</p>
      </header>

      <div className="flex flex-col gap-6 px-6 pt-6">
        {bannerOpen && (
          <section className="flex items-start gap-3 rounded-lg bg-warning p-4 text-white">
            <WarningTriangleIcon className="mt-0.5 shrink-0" width={22} height={22} />
            <div className="flex flex-1 flex-col gap-1">
              <p className="text-body-md font-semibold">{actionRequired.title}</p>
              <p className="text-body-sm text-white/90">{actionRequired.body}</p>
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
          {stats.map((stat) => (
            <div
              key={stat.id}
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
                {active.map((item) => `${item.workerName} - ${item.jobTitle}`).join(", ")}
              </span>
            </span>
            <ChevronDownIcon
              className={cn("mt-1 shrink-0 text-grey-900 transition-transform", listOpen && "rotate-180")}
            />
          </button>

          {listOpen &&
            active.map((guarantee) => (
              <GuaranteeCard key={guarantee.id} guarantee={guarantee} />
            ))}
        </section>

        <section className="flex flex-col overflow-hidden rounded-lg border border-stroke">
          <h2 className="bg-primary-25 px-4 py-4 text-body-md font-medium text-grey-900">
            Recent activity
          </h2>
          <ul className="flex flex-col">
            {recentActivity.map((entry) => (
              <li
                key={entry.id}
                className="flex items-start gap-3 border-t border-stroke px-4 py-3 first:border-t-0"
              >
                <CheckIcon className="mt-1 shrink-0 text-grey-900" />
                <span className="flex flex-col gap-0.5">
                  <span className="text-body-sm font-medium text-grey-900">{entry.label}</span>
                  <span className="text-body-sm text-grey-600">{entry.at}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}

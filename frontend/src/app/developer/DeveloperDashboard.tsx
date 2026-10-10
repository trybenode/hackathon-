"use client";

import Link from "next/link";
import { BarChartIcon, BuildingIcon, ImageIcon, TickIcon, UserIcon } from "@/components/developer/icons";
import { UsageChart } from "@/components/developer/UsageChart";
import { useDeveloper } from "@/components/developer/useDeveloper";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { DeveloperDashboard as Dashboard } from "@/lib/developer";

function VerificationCard({ data }: { data: Dashboard }) {
  const reviewing = data.kyb_status === "under_review";
  return (
    <section className="flex flex-col gap-4 rounded-lg bg-grey-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-body-md font-medium text-grey-900">Account verification</h2>
          <p className="text-xs leading-4 text-grey-900">Complete KYB verifications to unlock Api access.</p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-pill px-3 py-0.5 text-body-sm",
            reviewing ? "bg-warning-light text-grey-900" : "bg-error-light text-error",
          )}
        >
          {reviewing ? "Under review" : "Action required"}
        </span>
      </div>

      <div className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-3">
        <div className="flex items-start gap-3">
          <BuildingIcon className="mt-0.5 shrink-0 text-grey-900" />
          <div className="flex flex-col gap-1">
            <p className="text-body-md text-grey-900">Business verification (KYB)</p>
            <p className="text-xs leading-4 text-grey-900">
              {reviewing
                ? "Submitted. We'll unlock API access once your business is approved."
                : "Verify your Registered business"}
            </p>
          </div>
        </div>
        {data.kyb_status === "rejected" && data.review_note && (
          <p role="alert" className="text-body-sm text-error">
            {data.review_note}
          </p>
        )}
        {reviewing ? (
          <Button variant="outline" fullWidth disabled className="rounded-lg font-semibold">
            Complete KYB
          </Button>
        ) : (
          <Link href="/developer/verify">
            <Button variant="outline" fullWidth className="rounded-lg font-semibold">
              Complete KYB
            </Button>
          </Link>
        )}
      </div>
    </section>
  );
}

/** "Developer Dashboard": verification, usage, credentials and recent calls. */
export function DeveloperDashboard() {
  const { data, error } = useDeveloper();
  const approved = data?.kyb_status === "approved";
  const calls = data?.usage.total_calls ?? 0;

  return (
    <main className="mx-auto flex w-full max-w-md flex-col pb-10">
      <header className="flex items-start justify-between gap-3 border-b border-stroke px-6 pt-8 pb-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-body-lg font-semibold text-grey-900">Developer Dashboard</h1>
          <p className="text-body-sm text-grey-900">Manage verification and API integrations</p>
        </div>
        <Link href="/developer/profile" aria-label="Profile" className="mt-1 text-grey-900">
          <UserIcon />
        </Link>
      </header>

      {error && (
        <p role="alert" className="px-6 pt-6 text-body-sm text-error">
          {error}
        </p>
      )}
      {!data && !error && <p className="px-6 pt-6 text-body-sm text-grey-600">Loading…</p>}

      {data && (
        <div className="flex flex-col gap-8 px-6 pt-3">
          {!approved && <VerificationCard data={data} />}

          <section className="flex flex-col gap-4">
            <h2 className="text-body-md font-semibold text-grey-900">API usage overview</h2>
            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  label: "Total API calls",
                  value: data.usage.total_calls,
                  icon: <ImageIcon className="text-info" />,
                  tone: "bg-primary-50",
                },
                {
                  label: "Successful calls",
                  value: data.usage.successful_calls,
                  icon: <TickIcon className="text-success" />,
                  tone: "bg-success-light",
                },
              ].map((stat) => (
                <div key={stat.label} className="flex flex-col gap-3 rounded-xl border border-stroke bg-white p-4">
                  <span className={cn("flex h-10 w-10 items-center justify-center rounded-pill", stat.tone)}>
                    {stat.icon}
                  </span>
                  <span className="flex flex-col gap-1">
                    <span className="text-body-lg text-grey-900">{calls ? stat.value : "—"}</span>
                    <span className="text-body-sm text-grey-600">{stat.label}</span>
                  </span>
                </div>
              ))}
            </div>
            {!calls && <p className="text-xs leading-4 text-grey-900">Usage figures populate once API calls are available</p>}
          </section>

          <section className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-5">
            <div className="flex flex-col gap-1">
              <h2 className="text-body-md text-grey-900">API access</h2>
              <p className="text-xs leading-4 text-grey-900">
                {approved
                  ? "Create credentials to connect your application to our API"
                  : "Complete and receive approval for KYB to generate your API credentials"}
              </p>
            </div>
            {approved ? (
              <Link href="/developer/credentials">
                <Button fullWidth className="rounded-lg font-semibold">
                  Generate API credentials
                </Button>
              </Link>
            ) : (
              <Button
                fullWidth
                disabled
                variant="ghost"
                className="rounded-lg bg-grey-600/70 font-semibold text-white/85 disabled:opacity-100"
              >
                Generate API credentials
              </Button>
            )}
          </section>

          <section className="flex flex-col gap-4">
            <h2 className="text-body-md font-semibold text-grey-900">Recent API activity</h2>
            {calls > 0 ? (
              // A list of calls would push the chart down with every request,
              // so the card shows the chart alone for now.
              <div className="flex flex-col gap-3 rounded-xl border border-stroke bg-white px-3 pt-4 pb-2">
                <p className="px-2 text-body-sm text-grey-900">Calls over the last 14 days</p>
                <UsageChart daily={data.usage.daily} />
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 rounded-xl border border-stroke bg-white px-5 py-6 text-center">
                <BarChartIcon className="text-grey-800" />
                <p className="pt-2 text-body-md text-grey-900">No API Activity yet</p>
                <p className="text-xs leading-4 text-grey-900">
                  Your API request history will appear here after you start making calls
                </p>
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}

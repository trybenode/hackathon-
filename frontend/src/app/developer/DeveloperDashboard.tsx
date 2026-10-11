"use client";

import Link from "next/link";
import { useDeveloper } from "@/components/developer/DeveloperContext";
import { BarChartIcon, BuildingIcon, ImageIcon, KeyIcon, TickIcon } from "@/components/developer/icons";
import { PageHeader } from "@/components/developer/PageHeader";
import { UsageChart } from "@/components/developer/UsageChart";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { DeveloperDashboard as Dashboard } from "@/lib/developer";

function VerificationBanner({ data }: { data: Dashboard }) {
  const reviewing = data.kyb_status === "under_review";
  return (
    <section className="flex flex-col gap-4 rounded-xl bg-grey-50 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-4">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-pill bg-white">
          <BuildingIcon className="text-grey-900" />
        </span>
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-body-md font-medium text-grey-900">Business verification (KYB)</h2>
            <span
              className={cn(
                "rounded-pill px-3 py-0.5 text-xs",
                reviewing ? "bg-warning-light text-grey-900" : "bg-error-light text-error",
              )}
            >
              {reviewing ? "Under review" : "Action required"}
            </span>
          </div>
          <p className="text-body-sm text-grey-600">
            {reviewing
              ? "Submitted. We'll unlock API access once your business is approved."
              : "Complete KYB verification to unlock API access."}
          </p>
          {data.kyb_status === "rejected" && data.review_note && (
            <p role="alert" className="text-body-sm text-error">
              {data.review_note}
            </p>
          )}
        </div>
      </div>
      {reviewing ? (
        <Button variant="outline" disabled className="shrink-0 rounded-lg px-8 font-semibold">
          Complete KYB
        </Button>
      ) : (
        <Link href="/developer/verify" className="shrink-0">
          <Button variant="outline" className="w-full rounded-lg bg-white px-8 font-semibold">
            Complete KYB
          </Button>
        </Link>
      )}
    </section>
  );
}

function StatTile({ label, value, icon, tone }: { label: string; value: string; icon: React.ReactNode; tone: string }) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-stroke bg-white p-5">
      <span className={cn("flex h-10 w-10 items-center justify-center rounded-pill", tone)}>{icon}</span>
      <span className="flex flex-col gap-1">
        <span className="text-h3 font-semibold text-grey-900">{value}</span>
        <span className="text-body-sm text-grey-600">{label}</span>
      </span>
    </div>
  );
}

/** "Developer Dashboard": verification, usage and the way to API keys. */
export function DeveloperDashboard() {
  const { data, error } = useDeveloper();
  const approved = data?.kyb_status === "approved";
  const calls = data?.usage.total_calls ?? 0;
  const ok = data?.usage.successful_calls ?? 0;
  const keys = data?.credentials.length ?? 0;

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Developer Dashboard"
        description="Manage verification and API integrations"
        actions={
          approved && (
            <Link href="/developer/keys">
              <Button className="rounded-lg px-6 font-semibold">Manage API keys</Button>
            </Link>
          )
        }
      />

      {error && (
        <p role="alert" className="text-body-sm text-error">
          {error}
        </p>
      )}
      {!data && !error && <p className="text-body-sm text-grey-600">Loading…</p>}

      {data && (
        <div className="flex flex-col gap-8">
          {!approved && <VerificationBanner data={data} />}

          <section className="flex flex-col gap-4">
            <h2 className="text-body-lg font-semibold text-grey-900">API usage overview</h2>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatTile label="Total API calls" value={calls ? String(calls) : "—"} icon={<ImageIcon className="text-info" />} tone="bg-primary-50" />
              <StatTile label="Successful calls" value={calls ? String(ok) : "—"} icon={<TickIcon className="text-success" />} tone="bg-success-light" />
              <StatTile
                label="Success rate"
                value={calls ? `${Math.round((ok / calls) * 100)}%` : "—"}
                icon={<TickIcon className="text-success" />}
                tone="bg-success-light"
              />
              <StatTile label="Active API keys" value={approved ? String(keys) : "—"} icon={<KeyIcon className="text-info" />} tone="bg-primary-50" />
            </div>
            {!calls && <p className="text-xs leading-4 text-grey-900">Usage figures populate once API calls are available</p>}
          </section>

          <div className="grid gap-8 lg:grid-cols-3">
            <section className="flex flex-col gap-4 lg:col-span-2">
              <h2 className="text-body-lg font-semibold text-grey-900">Recent API activity</h2>
              {calls > 0 ? (
                <div className="flex flex-col gap-3 rounded-xl border border-stroke bg-white px-4 pt-5 pb-3">
                  <p className="px-2 text-body-sm text-grey-900">Calls over the last 14 days</p>
                  <UsageChart daily={data.usage.daily} />
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-stroke bg-white px-5 py-10 text-center">
                  <BarChartIcon className="text-grey-800" />
                  <p className="pt-2 text-body-md text-grey-900">No API Activity yet</p>
                  <p className="text-xs leading-4 text-grey-900">
                    Your API request history will appear here after you start making calls
                  </p>
                </div>
              )}
            </section>

            <section className="flex flex-col gap-4">
              <h2 className="text-body-lg font-semibold text-grey-900">API access</h2>
              <div className="flex flex-1 flex-col gap-4 rounded-xl border border-stroke bg-white p-5">
                <p className="text-body-sm text-grey-900">
                  {approved
                    ? keys
                      ? `You have ${keys} active API ${keys === 1 ? "key" : "keys"}. Create, limit, rotate or revoke them from API keys.`
                      : "Create credentials to connect your application to our API."
                    : "Complete and receive approval for KYB to generate your API credentials."}
                </p>
                <div className="mt-auto">
                  {approved ? (
                    <Link href="/developer/keys">
                      <Button variant="outline" fullWidth className="rounded-lg font-semibold">
                        {keys ? "Manage API keys" : "Create API key"}
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
                </div>
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}

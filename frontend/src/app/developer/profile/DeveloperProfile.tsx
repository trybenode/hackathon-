"use client";

import Link from "next/link";
import { TickIcon } from "@/components/developer/icons";
import { useDeveloper } from "@/components/developer/DeveloperContext";
import { PageHeader } from "@/components/developer/PageHeader";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { ReviewStatus } from "@/lib/developer";

const STATUS: Record<ReviewStatus, { label: string; tone: string }> = {
  approved: { label: "Verified", tone: "bg-success-light/60 text-grey-900" },
  under_review: { label: "Under review", tone: "bg-warning-light text-grey-900" },
  rejected: { label: "Rejected", tone: "bg-error-light text-error" },
  not_started: { label: "Not started", tone: "bg-grey-50 text-grey-600" },
};

function StatusPill({ status }: { status: ReviewStatus }) {
  const { label, tone } = STATUS[status];
  return (
    <span className={cn("flex items-center gap-1 rounded-md px-2 py-0.5 text-body-sm", tone)}>
      {status === "approved" && <TickIcon width={14} height={14} className="text-success" />}
      {label}
    </span>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-stroke py-5">
      <span className="text-body-sm text-grey-600">{label}</span>
      <span className="min-w-0 text-right text-body-sm font-medium break-words text-grey-900">{children}</span>
    </div>
  );
}

/** The developer's verified details; the name changes only through review. */
export function DeveloperProfile() {
  const { data, error } = useDeveloper();
  const canRequest = data?.kyc_status === "approved" && !data.name_change;

  return (
    <div className="flex max-w-3xl flex-col">
      <PageHeader title="Profile" description="Your verified details and business" />

      {error && (
        <p role="alert" className="text-body-sm text-error">
          {error}
        </p>
      )}

      {data && (
        <div className="flex flex-col overflow-hidden rounded-xl border border-stroke">
          <section className="flex items-center justify-between gap-3 border-b border-stroke px-6 py-6">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-pill bg-primary-500 text-white">
                <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor" aria-hidden>
                  <circle cx="12" cy="8.5" r="4" />
                  <path d="M4.5 19.5a7.5 5.5 0 0 1 15 0v.5h-15Z" />
                </svg>
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-body-md text-grey-900">{data.full_name ?? data.email}</span>
                <span className="text-xs leading-4 text-grey-600">Developer</span>
              </span>
            </div>
            {canRequest ? (
              <Link href="/developer/profile/name-change">
                <Button variant="outline" size="sm" className="rounded-lg px-6 font-semibold">
                  Request Change
                </Button>
              </Link>
            ) : (
              <Button variant="outline" size="sm" disabled className="rounded-lg px-6 font-semibold">
                {data.name_change ? "Change requested" : "Request Change"}
              </Button>
            )}
          </section>

          <section className="flex flex-col px-6 pt-8">
            <h2 className="text-body-md text-grey-900">Personal Information</h2>
            <Row label="Full Name">{data.full_name ?? "—"}</Row>
            <Row label="Email address">{data.email}</Row>
            {data.name_change && <Row label="Requested name">{data.name_change.new_name} · under review</Row>}
          </section>

          <section className="flex flex-col px-6 pt-10">
            <h2 className="text-body-md text-grey-900">Business Information</h2>
            <Row label="Company name">{data.business_name ?? "—"}</Row>
            <Row label="KYC status">
              <StatusPill status={data.kyc_status} />
            </Row>
            <Row label="KYB status">
              <StatusPill status={data.kyb_status} />
            </Row>
          </section>

          <div className="flex justify-center px-6 pt-12 pb-10">
            <Button
              size="lg"
              disabled
              variant="ghost"
              className="w-48 rounded-xl bg-grey-600/70 px-0 font-semibold text-white/85 disabled:opacity-100"
            >
              Save Changes
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import Image from "next/image";
import { useState, type ReactNode } from "react";
import { CalendarIcon, ChevronDownIcon, ClockIcon, LocationPinIcon, ProgressBar } from "@/components/ui";
import { ShieldIcon } from "@/components/worker/icons";
import { ScoreRing } from "@/components/worker/ScoreRing";
import { Timeline, type TimelineStep } from "@/components/worker/Timeline";
import { TrustBandBadge } from "@/components/worker/TrustBandBadge";
import { cn } from "@/lib/cn";
import { CONTAINER, SectionHeading } from "./Section";

// One sample job, seen without and with the trust layer.
const JOB = { title: "Home cleaning", place: "Lagos island, Lagos", time: "12:00PM", day: "29, Sep", pay: "₦25,000.00" };

const SCORES = [
  { label: "Quality", value: 89 },
  { label: "Completion", value: 87 },
  { label: "Reliability", value: 92 },
];

const DISPUTE: TimelineStep[] = [
  { label: "Negotiation", at: "30 Sep 2026\u00a0\u00a0\u00a012:04:32", note: "Both sides tried to agree directly", state: "done" },
  { label: "Evidence", at: "30 Sep 2026\u00a0\u00a0\u00a012:04:32", note: "3 photos and 1 video added", state: "done" },
  { label: "Awaiting decision", at: "30 Sep 2026\u00a0\u00a0\u00a012:04:32", note: "A reviewer has checked the evidence", state: "done" },
  { label: "Resolved", at: "30 Sep 2026\u00a0\u00a0\u00a012:04:32", note: "Decision recorded. Dispute closed.", state: "done" },
];

function Card({ title, className, children }: { title: string; className?: string; children: ReactNode }) {
  return (
    <article className={cn("flex w-full flex-col gap-4 rounded-xl border border-grey-200 bg-white p-6 shadow-2", className)}>
      <h3 className="border-b border-grey-400 pb-2 text-body-md font-semibold text-grey-900">{title}</h3>
      {children}
    </article>
  );
}

/** Jane A., the sample worker. */
function Worker() {
  return (
    <div className="flex items-center gap-4">
      <Image
        src="/landing/jane.webp"
        alt=""
        width={56}
        height={56}
        // Served as-is: Vercel Services doesn't route /_next/image.
        unoptimized
        className="h-14 w-14 shrink-0 rounded-pill object-cover"
      />
      <span className="flex flex-col">
        <span className="text-body-lg text-grey-900">Jane A.</span>
        <span className="text-xs leading-4 text-grey-600">Cleaner</span>
      </span>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-body-md text-grey-900">{label}</span>
      <span className="text-body-sm text-grey-800">{value}</span>
    </div>
  );
}

function OffPlatform() {
  return (
    <Card title="OFF platform" className="max-w-[363px]">
      <Worker />
      <div className="flex flex-col gap-3 border-t border-stroke pt-4">
        <h4 className="text-body-md font-semibold text-grey-900">{JOB.title}</h4>
        <span className="flex items-center gap-2 text-body-sm text-grey-800">
          <LocationPinIcon /> {JOB.place}
        </span>
        <span className="flex items-center gap-2 text-body-sm text-grey-800">
          <ClockIcon /> {JOB.time}
        </span>
        <span className="flex items-center gap-2 text-body-sm text-grey-800">
          <CalendarIcon width={14} height={14} /> {JOB.day}
        </span>
      </div>
      <div className="border-t border-stroke pt-3">
        <Detail label="Job Payment" value={JOB.pay} />
      </div>
      <div className="flex flex-col gap-3 border-t border-stroke pt-3">
        <Detail label="Trust score" value="No Trust score and band" />
        <Detail label="Payment protection" value="No payment protection" />
        <Detail label="Dispute" value="No detailed outcome recorded" />
      </div>
    </Card>
  );
}

function OnPlatform() {
  const [expanded, setExpanded] = useState(true);

  return (
    <Card title="ON platform" className="max-w-[413px]">
      <Worker />

      <div className="flex flex-col gap-4 rounded-lg border border-grey-200 p-4">
        <div className="flex items-center justify-between">
          <span className="text-body-sm text-grey-900">Trust Band</span>
          <TrustBandBadge band="High" />
        </div>
        <div className="flex items-center gap-3">
          <ScoreRing score={0.87} size={48} thickness={5} />
          <span className="flex flex-col">
            <span className="text-body-sm font-medium text-grey-900">Trust Score</span>
            <span className="text-xs leading-4 text-grey-900">Based on 42 verified outcomes</span>
          </span>
        </div>
        {expanded && (
          <dl className="flex flex-col gap-3">
            {SCORES.map((score) => (
              <div key={score.label} className="grid grid-cols-[88px_1fr] items-center gap-2">
                <dt className="text-body-sm text-grey-900">{score.label}</dt>
                <dd>
                  <ProgressBar value={score.value} showValue label={score.label} />
                </dd>
              </div>
            ))}
          </dl>
        )}
        <div className="flex items-center justify-between text-xs leading-4 text-grey-900">
          <span>Updated 2 days ago</span>
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded((open) => !open)}
            className="flex items-center gap-1 hover:text-primary-500"
          >
            {expanded ? "view less" : "view more"}
            <ChevronDownIcon width={14} height={14} className={cn(expanded && "rotate-180")} />
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <h4 className="text-body-md font-semibold text-grey-900">{JOB.title}</h4>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-body-sm text-grey-800">
          <span className="flex items-center gap-1.5">
            <LocationPinIcon /> {JOB.place}
          </span>
          <span className="flex items-center gap-1.5">
            <ClockIcon /> {JOB.time}
          </span>
          <span className="flex items-center gap-1.5">
            <CalendarIcon width={14} height={14} /> {JOB.day}
          </span>
        </div>
      </div>

      <section className="flex flex-col gap-2 rounded-lg bg-primary-25 p-4">
        <h4 className="flex items-center gap-2 text-body-md font-medium text-grey-900">
          <ShieldIcon className="text-info" />
          Payment Protected
        </h4>
        <p className="pl-7 text-body-md font-semibold text-grey-900">{JOB.pay}</p>
        <p className="pl-7 text-body-sm text-grey-900">Held securely until job is confirmed</p>
      </section>

      <section className="flex flex-col gap-4">
        <h4 className="text-body-md font-semibold text-grey-900">Dispute Progress</h4>
        <Timeline steps={DISPUTE} />
      </section>
    </Card>
  );
}

export function Comparison() {
  return (
    <section aria-labelledby="comparison-heading" className={`${CONTAINER} flex flex-col gap-10 py-16 lg:py-20`}>
      <div className="flex flex-col gap-3">
        <SectionHeading>
          <span id="comparison-heading">Side-by-side Comparison.</span>
        </SectionHeading>
        <p className="text-body-sm text-grey-800">
          See the difference the trust layer makes, from protected payments and verified worker reputations to
          safer hiring and greater accountability on every job.
        </p>
      </div>
      <div className="flex flex-col items-center gap-8 md:flex-row md:items-start md:justify-center">
        <OffPlatform />
        <OnPlatform />
      </div>
    </section>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ArrowLeftIcon, ArrowRightIcon, BriefcaseIcon } from "@/components/worker/icons";
import {
  ChartIcon,
  ChevronRightIcon,
  CredentialIcon,
  DownloadIcon,
  PeopleIcon,
  ShareIcon,
  WarningIcon,
} from "@/components/worker/recordIcons";
import { ScoreRing } from "@/components/worker/ScoreRing";
import { TrustBandBadge } from "@/components/worker/TrustBandBadge";
import { Button, CheckIcon } from "@/components/ui";
import { formatShortDate, initialsOf } from "@/lib/workerMock";
import {
  formatNairaWhole,
  formatNumericDate,
  formatPercent,
  workerRecord,
  type WorkerRecord,
} from "@/lib/workerRecordMock";
import { ShareRecordDialog } from "./ShareRecordDialog";

function Stat({
  icon,
  label,
  value,
  caption,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  caption?: string;
}) {
  return (
    <div className="flex min-h-[7.5rem] gap-2 rounded-lg border border-stroke bg-white p-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-pill bg-primary-25 text-info">
        {icon}
      </span>
      <div className="flex min-w-0 flex-col gap-1.5 pt-0.5">
        <p className="text-body-md whitespace-nowrap text-grey-900">{label}</p>
        <p className="text-body-lg font-semibold text-grey-900">{value}</p>
        {caption && <p className="text-body-sm text-grey-600">{caption}</p>}
      </div>
    </div>
  );
}

/**
 * Saves the record as JSON. A stand-in for the portable credentials export
 * (Abdul's side), whose signed format will replace this file.
 */
function exportRecord(record: WorkerRecord) {
  const blob = new Blob([JSON.stringify(record, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `portable-record-${record.name.toLowerCase().replace(/\s+/g, "-")}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function PortableRecord() {
  const router = useRouter();
  const [sharing, setSharing] = useState(false);
  const record = workerRecord;
  const { stats } = record;

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Portable Record</h1>
      </header>

      <div className="flex flex-col gap-6 px-6 pt-4">
        <section className="flex flex-col gap-4">
          <p className="text-xs leading-4 text-grey-900">Your verified work history</p>

          <div className="flex items-center gap-4">
            {/* The frame shows a photo; there is no upload yet, so initials
                stand in, as they do on Profile. */}
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-pill bg-primary-500 text-body-lg font-medium text-white">
              {initialsOf(record.name)}
            </span>
            <span className="flex flex-1 flex-col">
              <span className="text-body-lg text-grey-900">{record.shortName}</span>
              <span className="text-body-sm text-grey-600">{record.role}</span>
            </span>
            <TrustBandBadge band={record.assessment.band} />
          </div>

          <div className="flex items-center gap-4 rounded-lg bg-primary-25 p-3">
            <ScoreRing score={record.assessment.score} />
            <div className="flex flex-col gap-1.5">
              <p className="text-body-md font-semibold text-grey-900">Trust Score</p>
              <p className="text-xs leading-5 text-grey-900">
                Based on your verified work history and performance
              </p>
            </div>
          </div>

          <p className="px-2 text-body-sm text-grey-900">
            Last updated - {formatShortDate(record.lastUpdated)}
          </p>
        </section>

        {/* No design yet for the credentials list, so the row is shown but
            does not open anything. */}
        <div
          aria-disabled="true"
          className="flex items-center gap-4 rounded-xl border border-grey-400 px-6 py-4 text-grey-900"
        >
          <CredentialIcon className="shrink-0 text-info" />
          <span className="flex-1 text-body-md">{record.credentials.length} verified credentials</span>
          <ChevronRightIcon className="shrink-0" />
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          <Stat
            icon={<BriefcaseIcon width={20} height={20} />}
            label="Work history"
            value={String(stats.completedJobs)}
            caption="Completed jobs"
          />
          <Stat
            icon={<ChartIcon width={20} height={20} />}
            label="Performance"
            value={formatPercent(stats.onTimeRate)}
            caption="on-time"
          />
          <Stat
            icon={<PeopleIcon width={20} height={20} />}
            label="Repeat hires"
            value={String(stats.repeatHires)}
          />
          <Stat
            icon={<WarningIcon width={20} height={20} />}
            label="Dispute"
            value={String(stats.disputes)}
          />
        </div>

        <section className="flex flex-col gap-3">
          <div className="overflow-hidden rounded-lg bg-white shadow-1">
            <h2 className="bg-primary-25 px-3 py-4 text-body-md text-grey-900">Verified outcomes</h2>
            <ul>
              {record.outcomes.map((outcome) => (
                <li
                  key={outcome.id}
                  className="flex items-center gap-3 border-t border-stroke px-3 py-2"
                >
                  <CheckIcon className="shrink-0 text-grey-900" />
                  <span className="flex flex-1 flex-col">
                    <span className="text-body-sm font-medium text-grey-900">{outcome.title}</span>
                    <span className="text-body-sm text-grey-800">
                      {formatNumericDate(outcome.date)}· {formatNairaWhole(outcome.amount)}
                    </span>
                  </span>
                  <span className="text-xs leading-4 text-grey-900">{outcome.status}</span>
                </li>
              ))}
            </ul>
          </div>
          {/* No design yet for the full list. */}
          <span
            aria-disabled="true"
            className="flex items-center gap-2 self-end text-body-sm font-medium text-grey-900"
          >
            view all outcomes
            <ArrowRightIcon width={20} height={20} />
          </span>
        </section>

        <div className="flex flex-col items-center gap-3 pb-4">
          <Button
            size="lg"
            className="w-56 rounded-xl px-0 text-body-lg font-semibold"
            onClick={() => exportRecord(record)}
          >
            <DownloadIcon />
            Export record
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="w-56 rounded-xl px-0 text-body-lg font-semibold"
            onClick={() => setSharing(true)}
          >
            <ShareIcon />
            Share record
          </Button>
        </div>
      </div>

      <ShareRecordDialog open={sharing} onClose={() => setSharing(false)} />
    </main>
  );
}

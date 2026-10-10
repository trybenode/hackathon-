"use client";

import Link from "next/link";
import { LanguageSelector, useLanguage } from "@/components/history/LanguageProvider";
import { HistoryCounts } from "@/components/history/HistoryCounts";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ArrowLeftIcon, ArrowRightIcon, BriefcaseIcon } from "@/components/worker/icons";
import {
  ChartIcon,
  ChevronRightIcon,
  CredentialIcon,
  DownloadIcon,
  PeopleIcon,
  WarningIcon,
} from "@/components/worker/recordIcons";
import { OutcomeList } from "@/components/worker/OutcomeList";
import { RecordGate } from "@/components/worker/RecordGate";
import { useWorkerRecord } from "@/components/worker/useWorkerRecord";
import { ScoreRing } from "@/components/worker/ScoreRing";
import { TrustBandBadge } from "@/components/worker/TrustBandBadge";
import { AssessmentConfidence } from "@/components/worker/AssessmentConfidence";
import { ShareVerification } from "./ShareVerification";
import { PlatformApprovals } from "./PlatformApprovals";
import { Button } from "@/components/ui";
import { formatShortDate, initialsOf } from "@/lib/workerFormat";
import { exportCredentials, formatPercent, shortName } from "@/lib/workerRecord";

/** How many outcomes the record shows before "view all outcomes". */
const OUTCOME_PREVIEW = 3;

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
        <p className="text-body-md text-grey-900">{label}</p>
        <p className="text-body-lg font-semibold text-grey-900">{value}</p>
        {caption && <p className="text-body-sm text-grey-600">{caption}</p>}
      </div>
    </div>
  );
}

/** Saves the signed export, ready to import on another platform. */
async function saveExport(workerId: string, name: string) {
  const exported = await exportCredentials(workerId);
  const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `portable-record-${name.toLowerCase().replace(/\s+/g, "-")}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function PortableRecord() {
  const { t, dictionary } = useLanguage();
  const router = useRouter();
  const { data: record, error, loading, refresh } = useWorkerRecord();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function exportRecord() {
    if (!record) return;
    setExporting(true);
    setExportError(null);
    try {
      await saveExport(record.worker_id, record.name);
    } catch {
      setExportError("Could not export your record. Try again.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <main className="flex flex-col">
      <div className="px-6 pt-4"><LanguageSelector /></div>
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">{t("portable")}</h1>
      </header>

      <RecordGate loading={loading} error={error} onRetry={refresh} hasData={!!record}>
      {record && (
      <div className="flex flex-col gap-6 px-6 pt-4">
        <section className="flex flex-col gap-4">
          <p className="text-xs leading-4 text-grey-900">{t("verifiedRecords")}</p>

          <div className="flex items-center gap-4">
            {/* The frame shows a photo; there is no upload yet, so initials
                stand in, as they do on Profile. */}
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-pill bg-primary-500 text-body-lg font-medium text-white">
              {initialsOf(record.name)}
            </span>
            <span className="flex flex-1 flex-col">
              <span className="text-body-lg text-grey-900">{shortName(record.name)}</span>
              <span className="text-body-sm text-grey-600">{record.role}</span>
            </span>
            <TrustBandBadge band={record.assessment.band} />
          </div>

          <div className="flex items-center gap-4 rounded-lg bg-primary-25 p-3">
            <ScoreRing score={record.assessment.score} size={68} thickness={7} />
            <div className="flex flex-col gap-1.5">
              <p className="text-body-md font-semibold text-grey-900">{t("trustScore")}</p>
              <p className="text-xs leading-5 text-grey-900">
                {t("basedVerified")}
              </p>
            </div>
          </div>

          <AssessmentConfidence assessment={record.assessment} />
          <p className="text-body-sm text-grey-600">{record.self_declared_outcomes} self-declared records · {record.starting_rating_label ?? "No starting-history assessment"}. Self-declared history does not establish verified trust.</p>
          <p className="px-2 text-body-sm text-grey-900">
            Last updated - {formatShortDate(record.last_updated)}
          </p>
        </section>

        <Link
          href="/worker/profile/record/credentials"
          className="flex items-center gap-4 rounded-xl border border-grey-400 px-6 py-4 text-grey-900"
        >
          <CredentialIcon className="shrink-0 text-info" />
          <span className="flex-1 text-body-md">{t("credentials")}</span>
          <ChevronRightIcon className="shrink-0" />
        </Link>

        <div className="grid grid-cols-2 gap-2.5">
          <Stat
            icon={<BriefcaseIcon width={20} height={20} />}
            label={t("workHistory")}
            value={String(record.stats.completed_jobs)}
            caption={t("completedVerified")}
          />
          <Stat
            icon={<ChartIcon width={20} height={20} />}
            label={t("performance")}
            // There is no on-time data to measure, so this is the completion
            // rate: jobs completed out of those the worker was responsible for.
            value={
              record.stats.completion_rate === null ? "—" : formatPercent(record.stats.completion_rate)
            }
            caption="completed"
          />
          <Stat
            icon={<PeopleIcon width={20} height={20} />}
            label={t("repeatHires")}
            value={record.stats.repeat_hires === null ? t("unknown") : String(record.stats.repeat_hires)}
          />
          <Stat
            icon={<WarningIcon width={20} height={20} />}
            label={t("disputes")}
            value={record.stats.disputes === null ? t("unknown") : String(record.stats.disputes)}
          />
        </div>

        <section className="flex flex-col gap-3">
          <OutcomeList outcomes={record.outcomes.slice(0, OUTCOME_PREVIEW)} />
          <Link
            href="/worker/profile/record/outcomes"
            className="flex items-center gap-2 self-end text-body-sm font-medium text-grey-900"
          >
            view all outcomes
            <ArrowRightIcon width={20} height={20} />
          </Link>
        </section>

        <HistoryCounts counts={record.informal_history} dictionary={dictionary} />
        <ShareVerification summary={record.public_summary} refresh={refresh} />
        <Link href="/worker/profile/record/history" className="rounded-xl border border-stroke p-4">{t("newHistory")}</Link>
        {process.env.NEXT_PUBLIC_PLATFORM_APPROVALS_ENABLED === "true" && <PlatformApprovals />}
        <div className="flex flex-col items-center gap-3 pb-4">
          {exportError && (
            <p role="alert" className="text-body-sm text-error">
              {exportError}
            </p>
          )}
          <Button
            size="lg"
            className="w-56 rounded-xl px-0 text-body-lg font-semibold"
            disabled={exporting}
            onClick={exportRecord}
          >
            <DownloadIcon />
            {exporting ? t("processing") : t("export")}
          </Button>
        </div>
      </div>
      )}
      </RecordGate>
    </main>
  );
}

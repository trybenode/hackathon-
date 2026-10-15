"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";

import Link from "next/link";
import { AssessmentConfidence } from "@/components/worker/AssessmentConfidence";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { SignOutIcon } from "@/components/developer/icons";
import { LogoutDialog } from "@/components/worker/LogoutDialog";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { ChevronRightIcon, RecordIcon, VerifiedIcon } from "@/components/worker/recordIcons";
import { ScoreRing } from "@/components/worker/ScoreRing";
import { TrustBandBadge } from "@/components/worker/TrustBandBadge";
import { RecordGate } from "@/components/worker/RecordGate";
import { useWorkerRecord } from "@/components/worker/useWorkerRecord";
import { cn } from "@/lib/cn";
import { initialsOf } from "@/lib/workerFormat";

/** A row of the menu under the trust card: white, with a soft line under it. */
const MENU_ROW =
  "flex min-h-16 items-center gap-5 rounded-lg bg-white px-4 py-3 shadow-[0_1.5px_0_rgb(0_0_0/0.1)]";

export function Profile() {
  const { w } = useWorkerCopy();

  const router = useRouter();
  const { data: record, error, loading, refresh } = useWorkerRecord();
  const [loggingOut, setLoggingOut] = useState(false);

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label={w("Back")} onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">{w("Profile")}</h1>
      </header>

      <RecordGate loading={loading} error={error ? error : null} onRetry={refresh} hasData={!!record}>
      {record && (
      <div className="flex flex-col gap-8 px-6 pt-8">
        <section className="flex flex-col items-center gap-1 border-b border-stroke pb-5">
          <span className="mb-3 flex h-20 w-20 items-center justify-center rounded-pill bg-primary-500 text-h3 font-medium text-white">
            {initialsOf(record.name)}
          </span>
          <p className="flex items-center gap-1.5 text-body-md font-medium text-grey-900">
            {record.name}
            {record.identity_verified && (
              <VerifiedIcon className="text-success" aria-label={w("Identity verified")} role="img" />
            )}
          </p>
          <p className="text-body-sm text-grey-900">{record.role}</p>
          <p className="text-body-sm text-grey-600">{w("Identity:")}{record.identity_status === "sandbox" ? w("Sandbox check · demo") : record.identity_status.replace("_", " ")}</p>
        </section>

        <section className="flex flex-col gap-5 rounded-xl border border-stroke bg-white px-4 pt-5 pb-7">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-body-md text-grey-900">{w("Trust Band")}</h2>
            <TrustBandBadge band={record.assessment.band} />
          </div>
          <div className="flex items-center gap-4">
            <ScoreRing score={record.assessment.score} size={48} thickness={5} />
            <div className="flex flex-col gap-1">
              <p className="text-body-sm text-grey-900">{w("Trust Score")}</p>
              <p className="text-xs leading-4 text-grey-900">
                {w("Based on")}{record.verified_outcomes} {w("verified outcomes")}</p>
            </div>
          </div>
          <AssessmentConfidence assessment={record.assessment} />
        </section>

        <div className="flex flex-col">
          <Link
            href="/worker/profile/record"
            className={MENU_ROW}
          >
            <RecordIcon width={26} height={26} className="shrink-0 text-grey-800" />
            <span className="flex flex-1 flex-col gap-0.5">
              <span className="text-body-md font-medium text-grey-900">{w("Portable Record")}</span>
              <span className="text-body-sm text-grey-600">{w("Your verified work history")}</span>
            </span>
            <ChevronRightIcon className="shrink-0 text-grey-900" />
          </Link>
          <button
            type="button"
            onClick={() => setLoggingOut(true)}
            className={cn(MENU_ROW, "text-left")}
          >
            <SignOutIcon width={26} height={26} className="shrink-0 text-error-mid" />
            <span className="text-body-md font-medium text-error-mid">Log out</span>
          </button>
        </div>
      </div>
      )}
      </RecordGate>
      <LogoutDialog open={loggingOut} onClose={() => setLoggingOut(false)} />
    </main>
  );
}

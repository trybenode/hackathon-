"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { ChevronRightIcon, RecordIcon, VerifiedIcon } from "@/components/worker/recordIcons";
import { ScoreRing } from "@/components/worker/ScoreRing";
import { TrustBandBadge } from "@/components/worker/TrustBandBadge";
import { RecordGate } from "@/components/worker/RecordGate";
import { useWorkerRecord } from "@/components/worker/useWorkerRecord";
import { initialsOf } from "@/lib/workerMock";

export function Profile() {
  const router = useRouter();
  const { data: record, error, loading } = useWorkerRecord();

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Profile</h1>
      </header>

      <RecordGate loading={loading} error={error}>
      {record && (
      <div className="flex flex-col gap-8 px-6 pt-8">
        <section className="flex flex-col items-center gap-1 border-b border-stroke pb-5">
          <span className="mb-3 flex h-20 w-20 items-center justify-center rounded-pill bg-primary-500 text-h3 font-medium text-white">
            {initialsOf(record.name)}
          </span>
          <p className="flex items-center gap-1.5 text-body-md font-medium text-grey-900">
            {record.name}
            {record.identity_verified && (
              <VerifiedIcon className="text-success" aria-label="Identity verified" role="img" />
            )}
          </p>
          <p className="text-body-sm text-grey-900">{record.role}</p>
        </section>

        <section className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-body-sm font-medium text-grey-900">Trust Band</h2>
            <TrustBandBadge band={record.assessment.band} />
          </div>
          <div className="flex items-center gap-3">
            <ScoreRing score={record.assessment.score} size={44} thickness={5} />
            <div className="flex flex-col gap-0.5">
              <p className="text-body-sm text-grey-900">Trust Score</p>
              <p className="text-xs leading-4 text-grey-900">
                Based on {record.verified_outcomes} verified outcomes
              </p>
            </div>
          </div>
        </section>

        <Link
          href="/worker/profile/record"
          className="flex items-center gap-4 rounded-lg border-b border-stroke bg-white px-4 py-4 shadow-1"
        >
          <RecordIcon className="shrink-0 text-grey-800" />
          <span className="flex flex-1 flex-col gap-0.5">
            <span className="text-body-md font-medium text-grey-900">Portable Record</span>
            <span className="text-body-sm text-grey-600">Your verified work history</span>
          </span>
          <ChevronRightIcon className="shrink-0 text-grey-900" />
        </Link>
      </div>
      )}
      </RecordGate>
    </main>
  );
}

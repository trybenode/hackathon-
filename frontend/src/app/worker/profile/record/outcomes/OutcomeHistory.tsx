"use client";

import { useRouter } from "next/navigation";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { OutcomeList } from "@/components/worker/OutcomeList";
import { RecordGate } from "@/components/worker/RecordGate";
import { useWorkerRecord } from "@/components/worker/useWorkerRecord";

/** Every verified outcome on the worker's record, newest first. */
export function OutcomeHistory() {
  const router = useRouter();
  const { data, error, loading } = useWorkerRecord();

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Verified Outcomes</h1>
      </header>

      <RecordGate loading={loading} error={error}>
        {data && (
          <div className="px-6 pt-4 pb-4">
            <OutcomeList outcomes={data.outcomes} />
          </div>
        )}
      </RecordGate>
    </main>
  );
}

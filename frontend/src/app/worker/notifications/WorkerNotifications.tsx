"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { NotificationList } from "@/components/jobs/NotificationList";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { RecordGate } from "@/components/worker/RecordGate";
import { useWorkerResource } from "@/components/worker/useWorkerResource";
import { getMyNotifications } from "@/lib/workerJobs";

export function WorkerNotifications() {
  const router = useRouter();
  // The load time travels with the data, so Recent/Earlier is decided once.
  const load = useCallback(async () => ({ items: await getMyNotifications(), now: Date.now() }), []);
  const { data, error, loading } = useWorkerResource(load, "This account has no worker profile.");

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Notifications</h1>
      </header>
      <Link className="px-6 pt-4 underline" href="/worker/profile/record/verification">Verification and document review updates</Link>
      <RecordGate loading={loading} error={error}>
        {data && (
          <div className="px-6 pt-6 pb-6">
            <NotificationList items={data.items} now={data.now} hrefFor={(item) => `/worker/jobs/${item.job_id}`} />
          </div>
        )}
      </RecordGate>
    </main>
  );
}

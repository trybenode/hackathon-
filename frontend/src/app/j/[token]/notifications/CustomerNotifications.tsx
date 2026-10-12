"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { NotificationList, type JobNotification } from "@/components/jobs/NotificationList";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { getCustomerNotifications } from "@/lib/customerJobs";
import { ApiError } from "@/lib/guarantor";

/** The customer's notifications: their job's, since they have no account. */
export function CustomerNotifications({ token }: { token: string }) {
  const [data, setData] = useState<{ items: JobNotification[]; now: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCustomerNotifications(token)
      .then((items) => {
        if (!cancelled) setData({ items, now: Date.now() });
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(cause instanceof ApiError && cause.status === 404 ? "This job link is not valid." : "Could not load notifications.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col bg-white">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <Link href={`/j/${token}`} aria-label="Back to your job" className="text-grey-900">
          <ArrowLeftIcon />
        </Link>
        <h1 className="text-body-lg font-semibold text-grey-900">Notifications</h1>
      </header>
      <div className="px-6 pt-6 pb-6">
        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}
        {!data && !error && (
          <p role="status" className="text-body-sm text-grey-600">
            Loading…
          </p>
        )}
        {data && <NotificationList items={data.items} now={data.now} hrefFor={() => `/j/${token}`} />}
      </div>
    </main>
  );
}

"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";
import Link from "next/link";
import { CheckIcon, WarningTriangleIcon } from "@/components/ui";
import { ChevronRightIcon } from "@/components/worker/recordIcons";
import { formatRelative } from "@/lib/format";

export type JobNotification = {
  id: string;
  job_id: string;
  title: string;
  body: string;
  at: string;
  icon: "check" | "warning";
};

/** Anything from the last day is "Recent"; the rest is "Earlier". */
const RECENT_MS = 24 * 60 * 60 * 1000;

function Card({ item, href }: { item: JobNotification; href: string }) {
  const { w, language } = useWorkerCopy(true);

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-stroke bg-white p-4">
      <div className="flex items-start gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-pill bg-primary-50 text-primary-500">
          {item.icon === "warning" ? <WarningTriangleIcon width={22} height={22} /> : <CheckIcon width={22} height={22} />}
        </span>
        <div className="flex flex-1 flex-col gap-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-body-md font-medium text-grey-900">{w(item.title)}</h3>
            <span className="shrink-0 text-xs leading-5 text-grey-600">{language === "en" ? formatRelative(item.at) : new Intl.DateTimeFormat(`${language}-NG`, { day:"numeric", month:"short", hour:"numeric", minute:"2-digit", timeZone:"Africa/Lagos" }).format(new Date(item.at))}</span>
          </div>
          <p className="text-body-sm text-grey-600">{w(item.body)}</p>
        </div>
      </div>
      <Link href={href} className="flex items-center gap-1 self-end text-body-sm font-medium text-grey-900">
        {w("View")}<ChevronRightIcon width={18} height={18} />
      </Link>
    </article>
  );
}

/** The Notifications list both sides share, split into Recent and Earlier. */
export function NotificationList({
  items,
  hrefFor,
  now,
}: {
  items: JobNotification[];
  hrefFor: (item: JobNotification) => string;
  /** When the list was loaded, so render stays pure. */
  now: number;
}) {
  const { w } = useWorkerCopy(true);

  if (items.length === 0) {
    return <p className="text-body-sm text-grey-600">{w("No notifications yet.")}</p>;
  }

  const recent = items.filter((item) => now - new Date(item.at).getTime() < RECENT_MS);
  const earlier = items.filter((item) => now - new Date(item.at).getTime() >= RECENT_MS);

  return (
    <div className="flex flex-col gap-6">
      {[
        ["Recent", recent],
        ["Earlier", earlier],
      ].map(([label, group]) =>
        (group as JobNotification[]).length ? (
          <section key={label as string} className="flex flex-col gap-3">
            <h2 className="text-body-md text-grey-900">{w(label as string)}</h2>
            {(group as JobNotification[]).map((item) => (
              <Card key={item.id} item={item} href={hrefFor(item)} />
            ))}
          </section>
        ) : null,
      )}
    </div>
  );
}

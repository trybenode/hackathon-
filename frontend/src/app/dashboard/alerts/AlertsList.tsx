"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { BellIcon, CalendarIcon, CheckIcon } from "@/components/ui";
import { formatRelative } from "@/lib/format";
import { ApiError, getNotifications, type NotificationItem } from "@/lib/guarantor";

const ICONS: Record<NotificationItem["icon"], ReactNode> = {
  bell: <BellIcon width={20} height={20} className="text-primary-500" />,
  check: <CheckIcon width={20} height={20} className="text-primary-500" />,
  calendar: <CalendarIcon width={20} height={20} className="text-primary-500" />,
};

/** Anything older than this is filed under "Earlier". */
const RECENT_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

export function AlertsList() {
  const router = useRouter();
  const pathname = usePathname();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [now] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const loaded = await getNotifications();
        if (!cancelled) setItems(loaded);
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
          return;
        }
        setError("Could not load your notifications.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  // Captured once on mount: reading the clock during render is impure and
  // would regroup items on every re-render.
  const groups: { name: string; items: NotificationItem[] }[] = [
    {
      name: "Recent",
      items: items.filter((item) => now - new Date(item.at).getTime() < RECENT_WINDOW_MS),
    },
    {
      name: "Earlier",
      items: items.filter((item) => now - new Date(item.at).getTime() >= RECENT_WINDOW_MS),
    },
  ];

  return (
    <main className="flex flex-col">
      <header className="border-b border-stroke px-6 pt-8 pb-5">
        <h1 className="text-body-lg font-semibold text-grey-900">Notifications</h1>
      </header>

      <div className="flex flex-col gap-6 px-6 pt-6">
        {loading && (
          <p role="status" className="text-body-sm text-grey-600">
            Loading…
          </p>
        )}
        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}
        {!loading && !error && items.length === 0 && (
          <p className="text-body-sm text-grey-600">Nothing to report yet.</p>
        )}

        {groups.map((group) =>
          group.items.length === 0 ? null : (
            <section key={group.name} className="flex flex-col gap-3">
              <h2 className="text-body-sm text-grey-600">{group.name}</h2>
              {group.items.map((item) => (
                <article
                  key={item.id}
                  className="flex gap-3 rounded-xl border border-stroke bg-white p-4"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-pill bg-info-light">
                    {ICONS[item.icon]}
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <p className="text-body-md font-medium text-grey-900">{item.title}</p>
                    <p className="text-body-sm text-grey-600">{item.body}</p>
                    <p className="self-end text-xs leading-4 text-grey-600">
                      {formatRelative(item.at)}
                    </p>
                  </div>
                </article>
              ))}
            </section>
          ),
        )}
      </div>
    </main>
  );
}

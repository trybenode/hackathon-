import type { ReactNode } from "react";
import { BellIcon, CalendarIcon, CheckIcon } from "@/components/ui";
import { notifications, type Notification } from "@/lib/dashboardMock";

export const metadata = { title: "Notifications" };

const ICONS: Record<Notification["icon"], ReactNode> = {
  bell: <BellIcon width={20} height={20} className="text-primary-500" />,
  check: <CheckIcon width={20} height={20} className="text-primary-500" />,
  calendar: <CalendarIcon width={20} height={20} className="text-primary-500" />,
};

const GROUPS = ["Recent", "Earlier"] as const;

export default function AlertsPage() {
  return (
    <main className="flex flex-col">
      <header className="border-b border-stroke px-6 pt-8 pb-5">
        <h1 className="text-body-lg font-semibold text-grey-900">Notifications</h1>
      </header>

      <div className="flex flex-col gap-6 px-6 pt-6">
        {GROUPS.map((group) => {
          const items = notifications.filter((item) => item.group === group);
          if (items.length === 0) return null;

          return (
            <section key={group} className="flex flex-col gap-3">
              <h2 className="text-body-sm text-grey-600">{group}</h2>
              {items.map((item) => (
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
                    <p className="self-end text-xs leading-4 text-grey-600">{item.at}</p>
                  </div>
                </article>
              ))}
            </section>
          );
        })}
      </div>
    </main>
  );
}

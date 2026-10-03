"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BellIcon, DocumentIcon, HomeIcon, PersonIcon } from "@/components/ui";
import { cn } from "@/lib/cn";

const TABS = [
  { href: "/dashboard", label: "Home", Icon: HomeIcon },
  { href: "/dashboard/guarantees", label: "Guarantees", Icon: DocumentIcon },
  { href: "/dashboard/alerts", label: "Alerts", Icon: BellIcon, dot: true },
  { href: "/dashboard/profile", label: "Profile", Icon: PersonIcon },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Dashboard"
      className="fixed inset-x-0 bottom-0 mx-auto flex w-full max-w-md justify-around border-t border-stroke bg-white px-2 pt-3 pb-5"
    >
      {TABS.map(({ href, label, Icon, dot }) => {
        // Only the home tab needs an exact match; the others own their subtrees.
        const active = href === "/dashboard" ? pathname === href : pathname.startsWith(href);

        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex flex-1 flex-col items-center gap-1 text-xs leading-4",
              active ? "text-primary-500" : "text-grey-600",
            )}
          >
            <span className="relative">
              <Icon width={22} height={22} />
              {dot && (
                <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-pill bg-primary-500" />
              )}
            </span>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

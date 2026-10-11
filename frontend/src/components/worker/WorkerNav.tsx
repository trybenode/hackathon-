"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { BriefcaseIcon, HomeIcon, PersonIcon } from "./icons";

const TABS = [
  { label: "Home", href: "/worker", Icon: HomeIcon },
  { label: "Jobs", href: "/worker/jobs", Icon: BriefcaseIcon },
  { label: "Profile", href: "/worker/profile", Icon: PersonIcon },
];

export function WorkerNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Worker"
      className="fixed inset-x-0 bottom-0 mx-auto flex w-full max-w-md justify-around border-t border-stroke bg-white px-2 pt-3 pb-5"
    >
      {TABS.map(({ label, href, Icon }) => {
        // Home is exact; the other tabs own their subtrees.
        const active =
          href !== null && (href === "/worker" ? pathname === href : pathname.startsWith(href));
        const classes = cn(
          "flex flex-1 flex-col items-center gap-1 text-xs leading-4",
          active ? "text-primary-500" : "text-grey-600",
        );

        return href ? (
          <Link key={label} href={href} aria-current={active ? "page" : undefined} className={classes}>
            <Icon />
            {label}
          </Link>
        ) : (
          <span key={label} aria-disabled="true" className={cn(classes, "cursor-default")}>
            <Icon />
            {label}
          </span>
        );
      })}
    </nav>
  );
}

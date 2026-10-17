"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  ActivityIcon,
  BookIcon,
  CloseIcon,
  GridIcon,
  KeyIcon,
  MenuIcon,
  ShieldCheckIcon,
  SignOutIcon,
  UserIcon,
} from "@/components/developer/icons";
import { DeveloperProvider, useDeveloper } from "@/components/developer/DeveloperContext";
import { BRAND_NAME } from "@/lib/brand";
import { cn } from "@/lib/cn";
import type { ReviewStatus } from "@/lib/developer";
import { signOut } from "@/lib/guarantor";

const NAV = [
  { href: "/developer", label: "Dashboard", icon: GridIcon },
  { href: "/developer/keys", label: "API keys", icon: KeyIcon },
  { href: "/developer/activity", label: "Activity", icon: ActivityIcon },
  { href: "/developer/verify", label: "Verification", icon: ShieldCheckIcon },
  { href: "/developer/reviews", label: "Onboarding reviews", icon: ShieldCheckIcon },
  { href: "/developer/docs", label: "Docs", icon: BookIcon },
  { href: "/developer/profile", label: "Profile", icon: UserIcon },
];

const VERIFICATION: Record<ReviewStatus, { label: string; tone: string }> = {
  not_started: { label: "Action required", tone: "bg-error-light text-error" },
  rejected: { label: "Action required", tone: "bg-error-light text-error" },
  under_review: { label: "In review", tone: "bg-warning-light text-grey-900" },
  approved: { label: "Verified", tone: "bg-success-light text-grey-900" },
};

function isActive(pathname: string, href: string) {
  return href === "/developer" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

function Brand() {
  return (
    <Link href="/developer" className="flex items-center gap-2">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-500 text-body-md font-semibold text-white">
        {BRAND_NAME[0]}
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-body-md font-semibold text-grey-900">{BRAND_NAME}</span>
        <span className="text-xs text-grey-600">Developers</span>
      </span>
    </Link>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data } = useDeveloper();
  const verification = data ? VERIFICATION[data.kyb_status] : null;

  async function leave() {
    await signOut().catch(() => undefined);
    router.push("/sign-in");
  }

  return (
    <div className="flex h-full flex-col gap-8 px-4 py-6">
      <div className="px-2">
        <Brand />
      </div>

      <nav aria-label="Developer" className="flex flex-col gap-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-body-sm transition-colors",
                active ? "bg-primary-50 font-medium text-grey-900" : "text-grey-800 hover:bg-grey-50",
              )}
            >
              <Icon className={active ? "text-primary-500" : "text-grey-600"} />
              <span className="flex-1">{label}</span>
              {href === "/developer/verify" && verification && (
                <span className={cn("rounded-pill px-2 py-0.5 text-xs", verification.tone)}>{verification.label}</span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto flex flex-col gap-2 border-t border-stroke pt-4">
        {data && <p className="truncate px-3 text-xs text-grey-600">{data.email}</p>}
        <button
          type="button"
          onClick={leave}
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-body-sm text-grey-800 hover:bg-grey-50"
        >
          <SignOutIcon className="text-grey-600" />
          Sign out
        </button>
      </div>
    </div>
  );
}

/**
 * The developer portal: a sidebar on desktop, a menu button on smaller
 * screens, and the page beside it. Loads the dashboard once for every page.
 */
export function DeveloperShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <DeveloperProvider>
      <div className="min-h-dvh bg-white lg:flex">
        <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 border-r border-stroke bg-white lg:block">
          <Sidebar />
        </aside>

        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-stroke bg-white px-4 py-3 lg:hidden">
          <Brand />
          <button type="button" aria-label="Open menu" onClick={() => setOpen(true)} className="text-grey-900">
            <MenuIcon />
          </button>
        </header>

        {open && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <button
              type="button"
              aria-label="Close menu"
              className="absolute inset-0 bg-grey-900/40"
              onClick={() => setOpen(false)}
            />
            <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-white shadow-3">
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="absolute top-5 right-4 text-grey-900"
              >
                <CloseIcon />
              </button>
              <Sidebar onNavigate={() => setOpen(false)} />
            </div>
          </div>
        )}

        <main className="min-w-0 flex-1">
          <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-8 lg:py-10">{children}</div>
        </main>
      </div>
    </DeveloperProvider>
  );
}

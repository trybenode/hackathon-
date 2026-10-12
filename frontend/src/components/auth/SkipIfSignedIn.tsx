"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { getSignedInUser, landingPathFor, type SignedInUser } from "@/lib/guarantor";

/**
 * Where an already signed-in visitor belongs instead of a sign-in or sign-up
 * form, or null to show the form after all.
 *
 * - "landing": anyone signed in goes to their own side of the app.
 * - "worker": a worker goes to their unfinished step or Home; others stay to
 *   add a worker profile to their account.
 * - "developer": a developer goes to the dashboard; others stay to sign up.
 */
export type SkipTo = "landing" | "worker" | "developer";

function destination(to: SkipTo, user: SignedInUser, next?: string): string | null {
  if (to === "landing") return next ?? landingPathFor(user);
  if (to === "worker") {
    if (!user.is_worker) return null;
    return user.onboarding_step ? `/join/${user.onboarding_step}` : "/worker";
  }
  return user.is_developer ? "/developer" : null;
}

/**
 * Wraps a sign-in or sign-up page: checks the session once, sends a visitor
 * who is already signed in on, and shows the page to everyone else.
 */
export function SkipIfSignedIn({ to, next, children }: { to: SkipTo; next?: string; children: ReactNode }) {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getSignedInUser()
      .then((user) => {
        if (cancelled) return;
        const target = destination(to, user, next);
        if (target) router.replace(target);
        else setChecking(false);
      })
      .catch(() => {
        // Not signed in (or the API is unreachable): show the form.
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [next, router, to]);

  // Blank for the moment the check takes, so the form never flashes past.
  return checking ? null : children;
}

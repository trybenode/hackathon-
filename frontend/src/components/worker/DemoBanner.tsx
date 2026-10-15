"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { getSignedInUser, signOut } from "@/lib/guarantor";

/**
 * Tops every worker screen while someone explores the live demo: says it's a
 * demo, and offers to start a real account.
 */
export function DemoBanner() {
  const router = useRouter();
  const [isDemo, setIsDemo] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSignedInUser()
      .then((user) => {
        if (!cancelled) setIsDemo(user.is_demo);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  async function startNow() {
    setLeaving(true);
    // Sign-up sends a signed-in worker back to Home, so the demo ends first.
    await signOut().catch(() => {});
    router.push("/join");
  }

  if (!isDemo) return null;

  return (
    <div className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-primary-100 bg-primary-50 px-6 py-3">
      <p className="text-body-sm text-grey-900">This is a demo account.</p>
      <Button size="sm" className="shrink-0 px-4" disabled={leaving} onClick={startNow}>
        Start now
      </Button>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SpinnerIcon } from "@/components/ui";
import { getSignedInUser, landingPathFor, startDemo } from "@/lib/guarantor";

/**
 * Opens the live demo: signs the visitor in as the read-only demo worker and
 * shows them that worker's Home. Someone already signed in as themselves goes
 * to their own side of the app instead, so the demo never signs them out.
 */
export function StartDemo() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function open() {
      const current = await getSignedInUser().catch(() => null);
      if (cancelled) return;
      if (current && !current.is_demo) {
        router.replace(landingPathFor(current));
        return;
      }
      try {
        await startDemo();
        if (!cancelled) router.replace("/worker");
      } catch {
        if (!cancelled) setFailed(true);
      }
    }

    void open();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col items-center justify-center gap-4 px-6 text-center">
      {failed ? (
        <>
          <p className="text-body-md text-grey-900">The demo isn&rsquo;t available right now.</p>
          <Link href="/join" className="text-body-md font-medium text-primary-500 underline">
            Create your account instead
          </Link>
        </>
      ) : (
        <>
          <SpinnerIcon className="animate-spin text-primary-500" width={28} height={28} />
          <p className="text-body-md text-grey-900">Opening the demo account…</p>
        </>
      )}
    </main>
  );
}

"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, CloseIcon } from "@/components/ui";
import { getInstrument, type Instrument } from "@/lib/guarantor";

/**
 * Shown after a guarantor declines a request.
 *
 * No Figma frame exists for this screen yet; it reuses the onboarding layout
 * so it can be restyled without rework when one arrives.
 */
export function DeclinedNotice({ instrumentId }: { instrumentId: string }) {
  const [instrument, setInstrument] = useState<Instrument | null>(null);

  useEffect(() => {
    let cancelled = false;

    // Only for the worker's name; the screen reads fine without it.
    getInstrument(instrumentId)
      .then((loaded) => {
        if (!cancelled) setInstrument(loaded);
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [instrumentId]);

  // Worker names often already end in a period ("Jane A."), which would
  // otherwise double up against the sentence.
  const workerName = instrument?.worker?.full_name?.replace(/\.$/, "");

  return (
    <main className="mx-auto flex w-full max-w-md flex-col">
      <div className="relative mt-6 aspect-[400/235] w-full overflow-hidden">
        <Image
          src="/guarantor-hero.webp"
          alt=""
          fill
          priority
          sizes="(max-width: 448px) 100vw, 448px"
          className="object-cover"
          style={{ objectPosition: "50% 37%" }}
        />
      </div>

      <div className="flex flex-col items-center gap-4 px-6 pt-10 pb-10 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-pill bg-error-light">
          <CloseIcon className="text-error" width={26} height={26} strokeWidth="2" />
        </span>

        <h1 className="text-h3 text-grey-900">Request declined</h1>

        <p className="text-body-md text-grey-600">
          You declined to stand as guarantor
          {workerName ? ` for ${workerName}` : ""}. We&rsquo;ve let them know, and nothing
          further is needed from you.
        </p>

        <Link href="/sign-in" className="mt-4">
          <Button variant="outline" size="lg" className="rounded-lg px-10">
            Go to my dashboard
          </Button>
        </Link>
      </div>
    </main>
  );
}

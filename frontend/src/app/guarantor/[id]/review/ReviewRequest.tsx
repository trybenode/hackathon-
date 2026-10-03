"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, CheckIcon, LocationPinIcon, Modal, Switch } from "@/components/ui";
import { cn } from "@/lib/cn";
import { ApiError, getInstrument, signInstrument, type Instrument } from "@/lib/guarantor";

const AGREEMENT_POINTS = [
  "Provide accurate information.",
  "Maintain valid contact details",
  "Respond if a guarantee event occurs",
];

/** Browsers cannot see their own public IP; the API records what it receives. */
const CLIENT_IP_PLACEHOLDER = "0.0.0.0";

export function ReviewRequest({ instrumentId }: { instrumentId: string }) {
  const router = useRouter();
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [decliningOpen, setDecliningOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** What to tell a guarantor whose request is no longer open to a decision. */
  function settledMessage(status: Instrument["status"]): string | null {
    switch (status) {
      case "Pending Signature":
      case "Pending Verification":
        return null;
      case "Active":
        return "You have already accepted this guarantee, and it is now active.";
      case "Declined":
        return "You declined this guarantee. Nothing further is needed.";
      case "Revoked":
        return "This request was withdrawn by the worker.";
      case "Expired":
        return "This request expired before it was signed.";
      default:
        return "This request is no longer awaiting your decision.";
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const loaded = await getInstrument(instrumentId);
        if (cancelled) return;

        // A guarantor who already accepted lands back here from their email
        // link; send them on to the step they stopped at rather than offering
        // an Accept that the API will refuse.
        if (loaded.status === "Pending Verification") {
          router.replace(`/guarantor/${instrumentId}/sign-in`);
          return;
        }

        setInstrument(loaded);
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof ApiError ? cause.message : "Could not load this request.");
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [instrumentId, router]);

  async function respond(accepted: boolean) {
    if (!instrument) return;
    setSubmitting(true);
    setError(null);

    try {
      await signInstrument(instrumentId, {
        signer_name: instrument.guarantor.full_name,
        signer_phone: instrument.guarantor.phone ?? "",
        accepted,
        signature_metadata: {
          ip: CLIENT_IP_PLACEHOLDER,
          user_agent: navigator.userAgent,
          timestamp: new Date().toISOString(),
        },
      });
      router.push(
        accepted
          ? `/guarantor/${instrumentId}/sign-in?email=${encodeURIComponent(instrument.guarantor.email ?? "")}`
          : `/guarantor/${instrumentId}/declined`,
      );
    } catch (cause) {
      // A 409 means the request moved on since this page loaded, most often
      // because it was already answered elsewhere.
      const stale = cause instanceof ApiError && cause.status === 409;
      setError(
        stale
          ? "This request has already been answered. Refresh to see its current state."
          : cause instanceof ApiError
            ? cause.message
            : "Could not record your response.",
      );
      setSubmitting(false);
      setDecliningOpen(false);
    }
  }

  const workerName = instrument?.worker?.full_name ?? "this worker";
  const settled = instrument ? settledMessage(instrument.status) : null;

  return (
    <main className="mx-auto flex w-full max-w-md flex-col">
      {/*
        The asset is a 1024x1536 canvas whose artwork occupies rows 344-1144,
        so it is cropped to the design's band: object-position keeps the top of
        the illustration in frame while the transparent margins are cut away.
      */}
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

      <div className="flex flex-col gap-6 px-6 pt-8 pb-10">
        <header className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="h-10 w-10 shrink-0 overflow-hidden rounded-pill bg-grey-200">
              {instrument?.worker?.avatar_url && (
                <Image
                  src={instrument.worker.avatar_url}
                  alt=""
                  width={40}
                  height={40}
                  className="h-10 w-10 object-cover"
                  unoptimized
                />
              )}
            </span>
            <span className="flex flex-col">
              <span className="text-body-md font-semibold text-grey-900">
                {instrument?.worker?.full_name ?? "…"}
              </span>
              <span className="text-body-sm text-grey-600">{instrument?.worker?.role ?? ""}</span>
            </span>
          </div>

          <div className="flex flex-col items-end gap-1 text-right">
            <span className="text-body-md text-grey-900">{instrument?.worker?.job_title ?? ""}</span>
            {instrument?.worker?.location && (
              <span className="flex items-center gap-1 text-body-sm text-grey-600">
                <LocationPinIcon className="shrink-0" />
                {instrument.worker.location}
              </span>
            )}
          </div>
        </header>

        <p className="text-body-md text-grey-900">
          You&rsquo;ll be acting as a guarantor for {workerName} under the terms of this agreement
        </p>

        <section className="flex flex-col gap-4">
          <h2 className="text-body-lg font-semibold text-grey-900">You agree to:</h2>
          <ul className="flex flex-col gap-4">
            {AGREEMENT_POINTS.map((point) => (
              <li key={point} className="flex items-start gap-3 text-body-md text-grey-900">
                <CheckIcon className="mt-1 shrink-0 text-success" />
                {point}
              </li>
            ))}
          </ul>
        </section>

        <hr className="border-stroke" />

        {settled ? (
          <p className="text-body-md text-grey-900">{settled}</p>
        ) : (
          <>
        <Switch
          checked={agreed}
          onChange={setAgreed}
          disabled={submitting}
          label={
            <>
              I agree to the guarantee{" "}
              <a href="/terms" className="text-primary-400 underline">
                terms and conditions
              </a>
            </>
          }
        />

        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}

        <div className="flex flex-col gap-3">
          <Button
            size="lg"
            fullWidth
            disabled={!agreed || submitting || !instrument}
            onClick={() => respond(true)}
            // The design greys the button out rather than fading the fill, so
            // the disabled colour has to win over the variant's background.
            className={cn("rounded-lg", !agreed && "bg-grey-600! text-white! opacity-100!")}
          >
            {submitting ? "Submitting…" : "Accept & Continue"}
          </Button>
          <Button
            size="lg"
            variant="outline"
            fullWidth
            className="rounded-lg"
            disabled={submitting}
            onClick={() => setDecliningOpen(true)}
          >
            Decline
          </Button>
        </div>
          </>
        )}
      </div>

      <Modal open={decliningOpen} onClose={() => setDecliningOpen(false)} title="Decline guarantee">
        <p className="text-body-md text-grey-900">
          Are you sure you want to decline this guarantee
        </p>
        <div className="mt-2 flex w-full gap-3">
          <Button
            variant="outline"
            fullWidth
            disabled={submitting}
            onClick={() => setDecliningOpen(false)}
          >
            Cancel
          </Button>
          <Button fullWidth disabled={submitting} onClick={() => respond(false)}>
            Decline
          </Button>
        </div>
      </Modal>
    </main>
  );
}

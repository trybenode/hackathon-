"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button, Input, NigeriaFlagIcon, Select } from "@/components/ui";
import { cn } from "@/lib/cn";
import { ApiError, getInstrument, submitIdentity } from "@/lib/guarantor";

const RELATIONSHIPS = [
  { value: "sibling", label: "Sibling" },
  { value: "parent", label: "Parent" },
  { value: "spouse", label: "Spouse" },
  { value: "colleague", label: "Colleague" },
  { value: "other", label: "Other" },
];

/** Nigerian NIN and BVN are both 11 digits. */
const ID_LENGTH = 11;

export function IdentityForm({ instrumentId }: { instrumentId: string }) {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  // The design shows the placeholder until the guarantor picks one.
  const [relationship, setRelationship] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep the guarantor on the step their instrument is actually at, so a
  // stale link cannot submit details the API will reject.
  useEffect(() => {
    let cancelled = false;

    async function guard() {
      try {
        const instrument = await getInstrument(instrumentId);
        if (cancelled) return;
        if (instrument.status === "Pending Signature") {
          router.replace(`/guarantor/${instrumentId}/review`);
        } else if (instrument.status !== "Pending Verification") {
          setError("This request is no longer awaiting your identity details.");
        }
      } catch {
        if (!cancelled) setError("Could not load this request.");
      }
    }

    void guard();
    return () => {
      cancelled = true;
    };
  }, [instrumentId, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const data = new FormData(event.currentTarget);
    const nin = String(data.get("nin") ?? "").trim();
    const bvn = String(data.get("bvn") ?? "").trim();

    if (nin.length !== ID_LENGTH || bvn.length !== ID_LENGTH) {
      setError(`NIN and BVN are each ${ID_LENGTH} digits.`);
      return;
    }

    setSubmitting(true);
    try {
      await submitIdentity(
        instrumentId,
        {
          first_name: String(data.get("first_name") ?? "").trim(),
          last_name: String(data.get("last_name") ?? "").trim(),
          // The dial code is fixed by the design; store the full number.
          phone: `+234${String(data.get("phone") ?? "").trim().replace(/^0+/, "")}`,
          address: String(data.get("address") ?? "").trim(),
          nin,
          bvn,
        },
        file,
      );
      router.push(`/guarantor/${instrumentId}/liveness`);
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : "Could not submit your details. Try again.",
      );
      setSubmitting(false);
    }
  }

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

      <form onSubmit={handleSubmit} className="flex flex-col gap-5 px-6 pt-8 pb-10">
        <div className="flex flex-col gap-1">
          <h1 className="text-body-lg font-semibold text-grey-900">Identity Information</h1>
          <p className="text-body-sm text-grey-600">
            We need to verify your identity before the guarantee can be activated.
          </p>
        </div>

        <Input name="first_name" label="First Name" placeholder="Input text" required />
        <Input name="last_name" label="Last Name" placeholder="Input text" required />

        <Select
          label="Relationship with  guarantee"
          placeholder="Input text"
          options={RELATIONSHIPS}
          value={relationship}
          onChange={setRelationship}
        />

        <Input
          name="phone"
          type="tel"
          inputMode="tel"
          label="Phone Number"
          placeholder="Input your phone"
          lead="+234"
          trailingIcon={<NigeriaFlagIcon />}
          required
        />

        <div className="grid grid-cols-2 gap-4">
          <Input
            name="nin"
            label="NIN"
            placeholder="Input text"
            inputMode="numeric"
            maxLength={ID_LENGTH}
            required
          />
          <Input
            name="bvn"
            label="BVN"
            placeholder="Input text"
            inputMode="numeric"
            maxLength={ID_LENGTH}
            required
          />
        </div>

        <Input name="address" label="Address" placeholder="Input text" required />

        <div className="flex flex-col gap-2">
          <span className="text-body-sm font-medium text-grey-900">Upload utility bill</span>
          <div className="flex items-stretch rounded-md border border-stroke">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className={cn(
                "shrink-0 rounded-l-md border border-primary-300 px-4 py-3 text-body-sm font-medium",
                "text-grey-900 outline-none focus-visible:ring-2 focus-visible:ring-primary-300",
              )}
            >
              Upload file
            </button>
            <span
              className={cn(
                "flex min-w-0 flex-1 items-center truncate px-4 text-body-sm",
                file ? "text-grey-900" : "text-grey-400",
              )}
            >
              {file?.name ?? "File name"}
            </span>
          </div>
          <input
            ref={fileRef}
            type="file"
            name="utility_bill"
            accept="image/jpeg,image/png,application/pdf"
            className="hidden"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <p className="text-body-sm text-grey-600">
            We&rsquo;ll never share your details. See our Privacy Policy.
          </p>
        </div>

        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}

        <Button type="submit" size="lg" disabled={submitting} className="self-end rounded-lg px-12">
          {submitting ? "Submitting…" : "Submit"}
        </Button>
      </form>
    </main>
  );
}

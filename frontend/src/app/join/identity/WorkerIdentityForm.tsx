"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { OnboardingHero } from "@/components/verification/OnboardingHero";
import { UtilityBillInput } from "@/components/verification/UtilityBillInput";
import { stepPath, useOnboarding } from "@/components/verification/useOnboarding";
import { Button, CalendarIcon, Input, NigeriaFlagIcon } from "@/components/ui";
import { ApiError, getSignedInUser } from "@/lib/guarantor";
import { submitWorkerIdentity } from "@/lib/onboarding";

/** Nigerian NIN and BVN are both 11 digits. */
const ID_LENGTH = 11;

/** Today as "YYYY-MM-DD" in the visitor's own time zone, the date picker's format. */
function today() {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** "Identity Information": the worker's details, sent to the identity provider. */
export function WorkerIdentityForm() {
  const router = useRouter();
  const { error: loadError } = useOnboarding("identity");
  const [email, setEmail] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const birthDateRef = useRef<HTMLInputElement>(null);

  // The email is the one they signed up with.
  useEffect(() => {
    getSignedInUser()
      .then((user) => setEmail(user.email))
      .catch(() => undefined);
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const data = new FormData(event.currentTarget);
    const field = (name: string) => String(data.get(name) ?? "").trim();
    const nin = field("nin");
    const bvn = field("bvn");
    // The picker gives "YYYY-MM-DD"; a typed-in future date is still possible.
    const birthDate = field("date_of_birth");

    if (!birthDate || birthDate >= today()) {
      setError("Choose your date of birth.");
      return;
    }
    if (nin.length !== ID_LENGTH || bvn.length !== ID_LENGTH) {
      setError(`NIN and BVN are each ${ID_LENGTH} digits.`);
      return;
    }

    setSubmitting(true);
    try {
      const progress = await submitWorkerIdentity(
        {
          first_name: field("first_name"),
          last_name: field("last_name"),
          date_of_birth: birthDate,
          // The dial code is fixed by the design; store the full number.
          phone: `+234${field("phone").replace(/^0+/, "")}`,
          address: field("address"),
          nin,
          bvn,
        },
        file,
      );
      router.push(stepPath(progress.next_step));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not submit your details. Try again.");
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col">
      <OnboardingHero />

      <form onSubmit={handleSubmit} className="flex flex-col gap-5 px-6 pt-8 pb-10">
        <div className="flex flex-col gap-1">
          <h1 className="text-body-lg font-semibold text-grey-900">Identity Information</h1>
          <p className="text-body-sm text-grey-900">We need to verify your identity</p>
        </div>

        <h2 className="text-body-sm text-grey-900">Personal Information</h2>
        <Input name="first_name" label="First Name" placeholder="Input text" autoComplete="given-name" required />
        <Input name="last_name" label="Last Name" placeholder="Input text" autoComplete="family-name" required />
        <Input name="email" type="email" label="Email" placeholder="Input text" value={email} readOnly />
        {/* A calendar picker rather than typing. The browser's own icon is
            hidden in favour of the design's, and both it and the field open
            the picker. */}
        <Input
          ref={birthDateRef}
          name="date_of_birth"
          type="date"
          label="Date of birth"
          autoComplete="bday"
          min="1900-01-01"
          max={today()}
          onClick={(event) => event.currentTarget.showPicker?.()}
          className="[&::-webkit-calendar-picker-indicator]:hidden"
          trailingIcon={
            <button
              type="button"
              aria-label="Open calendar"
              onClick={() => birthDateRef.current?.showPicker?.()}
              className="text-inherit"
            >
              <CalendarIcon />
            </button>
          }
          required
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
        <Input name="address" label="Address" placeholder="Input text" autoComplete="street-address" required />

        <UtilityBillInput file={file} onChange={setFile} />

        <h2 className="pt-2 text-body-sm text-grey-900">Government Information</h2>
        <Input
          name="nin"
          label="NIN"
          placeholder="Enter your NIN"
          inputMode="numeric"
          maxLength={ID_LENGTH}
          required
        />
        <Input
          name="bvn"
          label="BVN"
          placeholder="Enter your Bvn"
          inputMode="numeric"
          maxLength={ID_LENGTH}
          required
        />
        <p className="text-body-sm text-grey-600">Your information is used only to verify your identity</p>

        {(error ?? loadError) && (
          <p role="alert" className="text-body-sm text-error">
            {error ?? loadError}
          </p>
        )}

        <Button type="submit" size="lg" disabled={submitting} className="self-end rounded-xl px-12">
          {submitting ? "Submitting…" : "Submit"}
        </Button>
      </form>
    </main>
  );
}

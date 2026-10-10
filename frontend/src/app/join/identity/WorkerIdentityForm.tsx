"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { OnboardingHero } from "@/components/verification/OnboardingHero";
import { UtilityBillInput } from "@/components/verification/UtilityBillInput";
import { stepPath, useOnboarding } from "@/components/verification/useOnboarding";
import { Button, CalendarIcon, Input, NigeriaFlagIcon } from "@/components/ui";
import { ApiError, getSignedInUser } from "@/lib/guarantor";
import { submitWorkerIdentity } from "@/lib/onboarding";

/** Nigerian NIN and BVN are both 11 digits. */
const ID_LENGTH = 11;

/** "DD/MM/YYYY" as typed, to "YYYY-MM-DD"; null when it is not a real past date. */
function parseBirthDate(value: string) {
  const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;
  const [, day, month, year] = match.map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  const real = date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
  if (!real || date >= new Date()) return null;
  return date.toISOString().slice(0, 10);
}

/** "Identity Information": the worker's details, sent to the identity provider. */
export function WorkerIdentityForm() {
  const router = useRouter();
  const { error: loadError } = useOnboarding("identity");
  const [email, setEmail] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    const birthDate = parseBirthDate(field("date_of_birth"));

    if (!birthDate) {
      setError("Enter your date of birth as DD/MM/YYYY.");
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
        <Input
          name="date_of_birth"
          label="Date of birth"
          placeholder="DD/MM/YYYY"
          inputMode="numeric"
          autoComplete="bday"
          trailingIcon={<CalendarIcon />}
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

"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { OnboardingHero } from "@/components/verification/OnboardingHero";
import { useOnboarding } from "@/components/verification/useOnboarding";
import { Button, Input, Select } from "@/components/ui";
import { ApiError, RELATIONSHIPS, type GuarantorRelationship } from "@/lib/guarantor";
import { inviteGuarantor, type GuarantorInvite } from "@/lib/onboarding";
import { GuarantorLinkDialog, type GuarantorDraft } from "./GuarantorLinkDialog";

function splitName(name: string) {
  const [first = "", ...rest] = name.trim().split(/\s+/);
  return { firstName: first, lastName: rest.join(" ") };
}

/**
 * "Add your guarantor": the worker names who will vouch for them and gets a
 * link to send. Skip goes Home, where job creation stays locked until a
 * guarantor is active.
 */
export function AddGuarantor() {
  const router = useRouter();
  const { data, error: loadError } = useOnboarding("guarantor");
  const [relationship, setRelationship] = useState<string | null>(null);
  const [draft, setDraft] = useState<GuarantorDraft | null>(null);
  const [created, setCreated] = useState<GuarantorInvite | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // A worker coming back with a link already out sees that link again;
  // closing it leaves them free to send a new one.
  const waiting = data?.invite && data.guarantor === "pending" && !dismissed ? data.invite : null;
  const invite = created ?? (draft ? null : waiting);
  const shown: GuarantorDraft | null =
    draft ??
    (invite
      ? { ...splitName(invite.name), relationship: invite.relationship as GuarantorRelationship }
      : null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (!relationship) {
      setFormError("Choose how your guarantor knows you.");
      return;
    }
    setFormError(null);
    setError(null);
    setDraft({
      firstName: String(form.get("first_name") ?? "").trim(),
      lastName: String(form.get("last_name") ?? "").trim(),
      relationship: relationship as GuarantorRelationship,
    });
  }

  async function generate() {
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      setCreated(await inviteGuarantor(draft.firstName, draft.lastName, draft.relationship));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not create the link. Try again.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (data?.guarantor === "active") router.replace("/worker");
  }, [data, router]);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col">
      <OnboardingHero />

      <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-5 px-6 pt-8 pb-10">
        <div className="flex flex-col gap-1">
          <h1 className="text-body-lg font-semibold text-grey-900">Add your guarantor</h1>
          <p className="text-body-sm text-grey-900">
            Your guarantor will confirm their identity and agree to vouch for you
          </p>
        </div>

        <h2 className="text-body-sm text-grey-900">Personal Information</h2>
        <Input name="first_name" label="First Name" placeholder="Input text" required />
        <Input name="last_name" label="Last Name" placeholder="Input text" required />
        <Select
          label="Relationship with  guarantee"
          placeholder="Select"
          options={RELATIONSHIPS}
          value={relationship}
          onChange={setRelationship}
        />

        {(formError ?? loadError) && (
          <p role="alert" className="text-body-sm text-error">
            {formError ?? loadError}
          </p>
        )}

        <div className="mt-auto flex items-center justify-between gap-4 pt-6">
          <Button
            type="button"
            variant="outline"
            size="lg"
            className="rounded-xl px-10"
            onClick={() => router.push("/worker")}
          >
            Skip
          </Button>
          <Button type="submit" size="lg" className="rounded-xl px-12" disabled={!data}>
            Submit
          </Button>
        </div>
      </form>

      {shown && (
        <GuarantorLinkDialog
          open
          draft={shown}
          invite={invite}
          busy={busy}
          error={error}
          onCancel={() => setDraft(null)}
          onDismiss={() => {
            setDismissed(true);
            setCreated(null);
            setDraft(null);
          }}
          onGenerate={generate}
          onDone={() => router.push("/worker")}
        />
      )}
    </main>
  );
}

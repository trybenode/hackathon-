"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ChoiceList } from "@/components/developer/ChoiceList";
import { DocumentUpload } from "@/components/developer/DocumentUpload";
import { useDeveloper } from "@/components/developer/DeveloperContext";
import { Button, Input } from "@/components/ui";
import { NAME_CHANGE_REASONS, requestNameChange } from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

type Reason = (typeof NAME_CHANGE_REASONS)[number]["value"];

/** "Request name change": the verified name changes only after review. */
export function NameChangeRequest() {
  const router = useRouter();
  const { data, error: loadError } = useDeveloper();
  const [newName, setNewName] = useState("");
  const [reason, setReason] = useState<Reason>("correction");
  const [document, setDocument] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await requestNameChange(newName.trim(), reason, document);
      router.push("/developer/profile");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not send your request. Try again.");
      setBusy(false);
    }
  }

  const failure = error ?? loadError;

  return (
    <main className="mx-auto flex w-full max-w-md flex-col px-6 pt-8 pb-10">
      <form onSubmit={submit} className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-body-lg font-semibold text-grey-900">Request name change</h1>
          <p className="text-xs leading-4 text-grey-900">
            Your name is linked to your identity verification. Submit your updated details for review
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-body-sm font-medium text-grey-600">Current Verified Name</span>
          <p className="rounded-xl bg-grey-50 px-4 py-3 text-body-md text-grey-800">{data?.full_name ?? "—"}</p>
        </div>

        <div className="flex flex-col gap-2">
          <Input
            label="New Legal Name"
            placeholder="Input text"
            autoComplete="name"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            required
          />
          <p className="text-body-sm text-grey-600">Enter your name exactly as it appears on your official identity document</p>
        </div>

        <ChoiceList legend="Reason for change" options={NAME_CHANGE_REASONS} value={reason} onChange={setReason} />

        <DocumentUpload
          heading="Supporting document"
          title="Upload supporting document."
          file={document}
          onChange={setDocument}
        />

        {failure && (
          <p role="alert" className="text-body-sm text-error">
            {failure}
          </p>
        )}

        <Button type="submit" size="lg" disabled={busy || !data} className="self-end rounded-xl px-10">
          {busy ? "Submitting…" : "Submit request"}
        </Button>
      </form>
    </main>
  );
}

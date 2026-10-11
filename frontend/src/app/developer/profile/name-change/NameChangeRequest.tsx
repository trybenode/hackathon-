"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { ChoiceList } from "@/components/developer/ChoiceList";
import { PageHeader } from "@/components/developer/PageHeader";
import { DocumentUpload } from "@/components/developer/DocumentUpload";
import { useDeveloper } from "@/components/developer/DeveloperContext";
import { Button, Input } from "@/components/ui";
import { NAME_CHANGE_REASONS, requestNameChange } from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

type Reason = (typeof NAME_CHANGE_REASONS)[number]["value"];

/** "Request name change": the verified name changes only after review. */
export function NameChangeRequest() {
  const router = useRouter();
  const { data, error: loadError, reload } = useDeveloper();
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
      reload();
      router.push("/developer/profile");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not send your request. Try again.");
      setBusy(false);
    }
  }

  const failure = error ?? loadError;

  return (
    <div className="flex max-w-2xl flex-col">
      <PageHeader
        title="Request name change"
        description="Your name is linked to your identity verification. Submit your updated details for review"
        actions={
          <Link href="/developer/profile">
            <Button variant="outline" className="rounded-lg px-6">
              Cancel
            </Button>
          </Link>
        }
      />
      <form onSubmit={submit} className="flex flex-col gap-6">

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
    </div>
  );
}

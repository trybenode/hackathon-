"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";

import { useState } from "react";
import { RadioGroup } from "@/components/worker/RadioGroup";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button, FileDropzone, FileItem, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";

const COMPLAINT_LIMIT = 234;
const MAX_FILES = 5;

/**
 * "Report an issue" for either side: the reasons differ, the rest is shared.
 * Evidence is optional, images or short video.
 */
export function ReportIssueDialog<T extends string>({
  open,
  onClose,
  reasons,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  reasons: readonly T[];
  /** Resolves when the report is filed; rejects with a message to show. */
  onSubmit: (reason: T, complaint: string, evidence: File[]) => Promise<void>;
}) {
  const { w } = useWorkerCopy(true);

  const [reason, setReason] = useState<T | null>(null);
  const [complaint, setComplaint] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // "Other" has no meaning without an explanation, so it needs the text.
  const canSubmit = reason !== null && (reason !== "Other" || complaint.trim().length > 0);

  function close() {
    setReason(null);
    setComplaint("");
    setFiles([]);
    setError(null);
    onClose();
  }

  async function submit() {
    if (!reason) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(reason, complaint.trim(), files);
      close();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not report the issue. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkerDialog open={open} onClose={close} label={w("Report an issue")} className="max-h-[90dvh] overflow-y-auto">
      <div className="flex flex-col gap-5">
        <h2 className="text-body-md font-semibold text-grey-900">{w("Report an issue")}</h2>
        <p className="text-body-lg text-grey-900">{w("What&rsquo;s the issue?")}</p>

        <RadioGroup legend="What's the issue?" options={reasons} value={reason} onChange={setReason} />

        <Textarea
          label={w("Enter Your Complaint")}
          placeholder={w("Input text")}
          rows={5}
          maxLength={COMPLAINT_LIMIT}
          showCount
          value={complaint}
          onChange={(event) => setComplaint(event.target.value)}
        />

        <div className="flex flex-col gap-2">
          <p className="text-body-sm text-grey-900">
            {w("Upload Evidence")}<span className="text-grey-600">{w("(if any)")}</span>
          </p>
          <FileDropzone
            title={w("Choose an image or video file")}
            hint={w("Or drag and drop it here")}
            buttonLabel={w("Upload File")}
            accept="image/jpeg,image/png,video/mp4,video/quicktime"
            multiple
            onFiles={(added) => setFiles((current) => [...current, ...added].slice(0, MAX_FILES))}
          />
          {files.map((file, index) => (
            <FileItem
              key={`${file.name}-${index}`}
              name={file.name}
              size={file.size}
              loaded={file.size}
              status="completed"
              onRemove={() => setFiles((current) => current.filter((_, at) => at !== index))}
            />
          ))}
        </div>

        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}

        <div className="flex gap-4">
          <Button variant="outline" size="lg" fullWidth className="min-w-0 rounded-xl px-0" onClick={close}>
            {w("Cancel")}</Button>
          <Button
            size="lg"
            fullWidth
            disabled={!canSubmit || busy}
            className={cn("min-w-0 rounded-xl px-0", !canSubmit && "opacity-50")}
            onClick={submit}
          >
            {busy ? w("Submitting…") : w("Submit")}
          </Button>
        </div>
      </div>
    </WorkerDialog>
  );
}

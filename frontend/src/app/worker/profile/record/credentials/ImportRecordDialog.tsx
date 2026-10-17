"use client";

import Link from "next/link";
import { useReviewCopy } from "@/components/admission/ReviewLanguage";
import { useState } from "react";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button, FileDropzone, FileItem, Switch } from "@/components/ui";
import { errorMessage } from "@/lib/portability";
import { importCredentials } from "@/lib/workerRecord";

/**
 * "Import Record": a portable record file exported earlier (Export record),
 * checked by the API before its verified outcomes join the worker's history.
 */
export function ImportRecordDialog({
  workerId,
  open,
  onClose,
  onImported,
}: {
  workerId: string;
  open: boolean;
  onClose: () => void;
  onImported: () => Promise<void> | void;
}) {
  const { t } = useReviewCopy();
  const [file, setFile] = useState<File | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  function close() {
    setFile(null);
    setAgreed(false);
    setError(null);
    setDone(null);
    onClose();
  }

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      let record: Record<string, unknown>;
      try {
        record = JSON.parse(await file.text());
      } catch {
        throw new Error("That file is not an exported record. Use the file Export record saved.");
      }
      const token = record.credential_token;
      if (typeof token !== "string" || !token) {
        throw new Error("That file has no signed record in it. Use the file Export record saved.");
      }
      // The server skips outcomes already on the record, so a re-import adds none.
      const result = await importCredentials(workerId, token);
      setDone(
        result.imported_outcomes === 0
          ? "Nothing new to add: every outcome in that record is already on your profile."
          : result.imported_outcomes === 1
            ? "1 verified outcome was added to your record."
            : `${result.imported_outcomes} verified outcomes were added to your record.`,
      );
      await onImported();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkerDialog open={open} onClose={close} label="Import Record">
      <div className="flex flex-col gap-5">
        <h2 className="text-body-md font-semibold text-grey-900">{t("signed")}</h2>
        <Link className="underline" href="/worker/profile/record/verification">{t("unsigned")}</Link>

        {done ? (
          <>
            <p role="status" className="text-body-sm text-grey-900">
              {done}
            </p>
            <Button size="lg" className="w-[calc(50%-0.5rem)] rounded-xl px-0" onClick={close}>
              Done
            </Button>
          </>
        ) : (
          <>
            <FileDropzone
              title="Choose a file or drag & drop it here."
              hint="Your exported portable record (.json)."
              buttonLabel="Browse File"
              accept="application/json,.json"
              onFiles={(files) => setFile(files[0] ?? null)}
            />
            {file && (
              <FileItem
                name={file.name}
                size={file.size}
                loaded={file.size}
                status="completed"
                onRemove={() => setFile(null)}
              />
            )}

            <Switch
              checked={agreed}
              onChange={setAgreed}
              label={
                <span className="text-body-sm text-grey-900">
                  I agree to the guarantee{" "}
                  <a href="/terms" className="text-primary-400">
                    terms and conditions
                  </a>
                </span>
              }
            />

            {error && (
              <p role="alert" className="text-body-sm text-error">
                {error}
              </p>
            )}

            <div className="flex gap-4">
              <Button variant="outline" size="lg" fullWidth className="min-w-0 rounded-xl px-0" onClick={close}>
                Cancel
              </Button>
              <Button
                size="lg"
                fullWidth
                className="min-w-0 rounded-xl px-0"
                disabled={!file || !agreed || busy}
                onClick={submit}
              >
                {busy ? "Importing…" : "Submit"}
              </Button>
            </div>
          </>
        )}
      </div>
    </WorkerDialog>
  );
}

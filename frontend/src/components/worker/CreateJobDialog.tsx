"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";

import { useState, type FormEvent } from "react";
import { CopyLinkButton } from "@/components/worker/CopyLinkButton";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button, CalendarIcon, CheckIcon, Input } from "@/components/ui";
import { ApiError } from "@/lib/guarantor";
import { createJob, type WorkerJob } from "@/lib/workerJobs";

/**
 * "Create a Job" (title, address, date and time, price), then "Your job link
 * has been successfully created!" with the link to copy and share.
 */
export function CreateJobDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated?: (job: WorkerJob) => void;
}) {
  const { w } = useWorkerCopy();

  const [title, setTitle] = useState("");
  const [address, setAddress] = useState("");
  const [when, setWhen] = useState("");
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<WorkerJob | null>(null);

  const amount = Number(price.replace(/[^0-9.]/g, ""));
  const ready = title.trim() && address.trim() && when && amount > 0;

  function close() {
    setTitle("");
    setAddress("");
    setWhen("");
    setPrice("");
    setError(null);
    setCreated(null);
    onClose();
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const job = await createJob({
        title: title.trim(),
        address: address.trim(),
        // The picker gives local time; send it with the browser's offset.
        scheduled_at: new Date(when).toISOString(),
        price: amount.toFixed(2),
      });
      setCreated(job);
      onCreated?.(job);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not create the job. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkerDialog open={open} onClose={close} label={created ? w("Job link created") : w("Create a Job")}>
      {created ? (
        <div className="flex flex-col gap-5">
          <div className="flex flex-col items-center gap-4 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-pill bg-primary-500">
              <CheckIcon className="text-white" width={28} height={28} />
            </span>
            <p className="text-body-md text-grey-900">{w("Your Job link has been successfully created!")}</p>
          </div>
          <p className="text-body-sm text-grey-600">{w("Job Link")}</p>
          <CopyLinkButton link={created.link} onCancel={close} />
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-5">
          <h2 className="text-body-md font-semibold text-grey-900">{w("Create a Job")}</h2>
          <Input label={w("Job Title")} placeholder={w("Input text")} value={title} onChange={(event) => setTitle(event.target.value)} />
          <Input label={w("Address")} placeholder={w("Input text")} value={address} onChange={(event) => setAddress(event.target.value)} />
          <Input
            label={w("Date & Time")}
            type="datetime-local"
            value={when}
            onChange={(event) => setWhen(event.target.value)}
            trailingIcon={<CalendarIcon width={18} height={18} />}
          />
          <Input
            label={w("Price")}
            placeholder={w("Input text")}
            inputMode="decimal"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
          />
          {error && (
            <p role="alert" className="text-body-sm text-error">
              {w(error)}
            </p>
          )}
          <Button
            type="submit"
            size="lg"
            disabled={!ready || busy}
            className="w-46 self-center rounded-xl px-0 text-body-md font-semibold"
          >
            {busy ? w("Generating…") : w("Generate link")}
          </Button>
        </form>
      )}
    </WorkerDialog>
  );
}

"use client";

import { useState } from "react";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { Button, DotIcon, Input, Select } from "@/components/ui";
import { cn } from "@/lib/cn";
import { RELATIONSHIPS, type GuarantorRelationship } from "@/lib/guarantor";
import type { GuarantorInvite } from "@/lib/onboarding";

export type GuarantorDraft = { firstName: string; lastName: string; relationship: GuarantorRelationship };

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <rect x="8" y="8" width="12" height="12" rx="2.5" />
      <path d="M16 8V6.5A2.5 2.5 0 0 0 13.5 4h-7A2.5 2.5 0 0 0 4 6.5v7A2.5 2.5 0 0 0 6.5 16H8" />
    </svg>
  );
}

/** Days until the link lapses, rounded up: "Link expires in 7 days". */
function daysLeft(expiresAt: string) {
  return Math.max(1, Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 86_400_000));
}

/**
 * "Review guarantor details": the worker checks the name and relationship and
 * generates the link; the same dialog then shows the link to copy and the
 * guarantor's verification status.
 */
export function GuarantorLinkDialog({
  open,
  draft,
  invite,
  busy,
  error,
  onCancel,
  onDismiss,
  onGenerate,
  onDone,
}: {
  open: boolean;
  draft: GuarantorDraft;
  /** Present once the link exists. */
  invite: GuarantorInvite | null;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  /** Closing the dialog once the link exists. */
  onDismiss: () => void;
  onGenerate: () => void;
  onDone: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (!invite) return;
    try {
      await navigator.clipboard.writeText(invite.link);
      setCopied(true);
    } catch {
      // Clipboard access can be refused; the link is still there to select.
    }
  }

  return (
    <WorkerDialog open={open} onClose={invite ? onDismiss : onCancel} label="Review guarantor details">
      <div className="flex flex-col gap-5">
        <h2 className="text-body-lg font-semibold text-grey-900">Review guarantor details</h2>

        <Input label="First Name" value={draft.firstName} readOnly />
        <Input label="Last Name" value={draft.lastName} readOnly />
        <Select label="Relationship with  guarantee" options={RELATIONSHIPS} value={draft.relationship} />

        {invite ? (
          <>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={copy}
                aria-label={copied ? "Link copied" : "Copy link"}
                className={cn("self-end", copied ? "text-success" : "text-grey-900")}
              >
                <CopyIcon />
              </button>
              <p className="min-h-24 rounded-lg bg-grey-50 px-4 py-3 text-body-md break-all text-grey-900 select-all">
                {invite.link}
              </p>
            </div>
            <p className="text-body-sm text-grey-900">
              Link expires in {daysLeft(invite.expires_at)} {daysLeft(invite.expires_at) === 1 ? "day" : "days"}
            </p>
            <div className="flex items-center justify-between gap-3 rounded-lg border border-stroke px-4 py-4">
              <span className="text-body-sm text-grey-900">Guarantor&rsquo;s Verification</span>
              <span className="flex items-center gap-1.5 text-body-sm text-grey-900">
                <DotIcon className={invite.status === "Active" ? "text-success" : "text-warning"} />
                {invite.status === "Active" ? "Verified" : "Pending"}
              </span>
            </div>
            <Button size="lg" className="self-end rounded-xl px-8" onClick={onDone}>
              Go to dashboard
            </Button>
          </>
        ) : (
          <>
            <p className="text-body-md text-grey-900">Make sure these details are correct before continuing.</p>
            {error && (
              <p role="alert" className="text-body-sm text-error">
                {error}
              </p>
            )}
            <div className="flex gap-4">
              <Button variant="outline" size="lg" fullWidth className="min-w-0 rounded-xl px-0" onClick={onCancel}>
                Cancel
              </Button>
              <Button size="lg" fullWidth className="min-w-0 rounded-xl px-0" disabled={busy} onClick={onGenerate}>
                {busy ? "Generating…" : "Generate link"}
              </Button>
            </div>
          </>
        )}
      </div>
    </WorkerDialog>
  );
}

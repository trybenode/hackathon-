"use client";

import { useId, useState } from "react";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { CopyIcon } from "@/components/worker/recordIcons";
import { Button, CheckIcon } from "@/components/ui";
import { cn } from "@/lib/cn";
import { SHARE_LINK_DAYS, SHARE_SCOPES, type ShareScope } from "@/lib/workerRecordMock";

/**
 * Pick what a viewer may see, then get a link to send them.
 *
 * The link is made up here; issuing real, expiring links is the portable
 * credentials export (Abdul's side), which this swaps to once it exists.
 */
export function ShareRecordDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const name = useId();
  const [scopes, setScopes] = useState<ShareScope[]>([]);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  function close() {
    setScopes([]);
    setLink(null);
    setCopied(false);
    onClose();
  }

  function toggle(scope: ShareScope) {
    setScopes((current) =>
      current.includes(scope) ? current.filter((s) => s !== scope) : [...current, scope],
    );
  }

  async function copy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      // Clipboard access can be refused; the link is still there to select.
    }
  }

  return (
    <WorkerDialog open={open} onClose={close} label="Share record">
      <div className="flex flex-col gap-5">
        <h2 className="text-body-md font-semibold text-grey-900">Share record</h2>
        <p className="text-body-lg text-grey-900">Choose what information you want to share</p>

        <fieldset className="flex flex-col gap-3">
          <legend className="sr-only">Choose what information you want to share</legend>
          {SHARE_SCOPES.map((scope) => {
            const id = `${name}-${scope}`;
            const checked = scopes.includes(scope);

            return (
              <label key={scope} htmlFor={id} className="flex cursor-pointer items-center gap-3">
                <input
                  id={id}
                  type="checkbox"
                  checked={checked}
                  // A link already issued covers what was chosen then.
                  disabled={link !== null}
                  onChange={() => toggle(scope)}
                  className="peer sr-only"
                />
                <span
                  aria-hidden
                  className={cn(
                    "flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-pill border transition-colors",
                    "peer-focus-visible:ring-2 peer-focus-visible:ring-primary-300 peer-focus-visible:ring-offset-2",
                    checked ? "border-primary-400 bg-primary-400 text-white" : "border-grey-400",
                  )}
                >
                  {checked && <CheckIcon width={12} height={12} />}
                </span>
                <span className="text-body-sm text-grey-900">{scope}</span>
              </label>
            );
          })}
        </fieldset>

        {link ? (
          <>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={copy}
                aria-label={copied ? "Link copied" : "Copy link"}
                className="flex items-center gap-1.5 self-end text-xs leading-4 text-grey-900"
              >
                {copied && <span aria-live="polite">Copied</span>}
                <CopyIcon />
              </button>
              <p className="min-h-32 rounded-lg bg-stroke/50 p-3 text-body-md break-all text-grey-900">
                {link}
              </p>
              <p className="text-xs leading-4 text-grey-900">Link expires in {SHARE_LINK_DAYS} days</p>
            </div>
            <Button variant="outline" size="lg" className="w-[calc(50%-0.5rem)] rounded-xl px-0" onClick={close}>
              Cancel
            </Button>
          </>
        ) : (
          <div className="flex gap-4">
            <Button variant="outline" size="lg" fullWidth className="min-w-0 rounded-xl px-0" onClick={close}>
              Cancel
            </Button>
            <Button
              size="lg"
              fullWidth
              className="min-w-0 rounded-xl px-0"
              disabled={scopes.length === 0}
              onClick={() => setLink(`https://demolink.com/r/${crypto.randomUUID().slice(0, 8)}`)}
            >
              Generate link
            </Button>
          </div>
        )}
      </div>
    </WorkerDialog>
  );
}

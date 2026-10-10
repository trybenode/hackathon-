"use client";

import { useState } from "react";
import { Button } from "@/components/ui";

/** The job link in a grey box, with a Copy button that says when it worked. */
export function CopyLinkButton({ link, onCancel }: { link: string; onCancel?: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      // Clipboard access can be refused; the link is still there to select.
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="rounded-lg bg-grey-200/60 px-3 py-3 text-body-sm break-all text-grey-900 select-all">{link}</p>
      <div className="flex gap-4">
        {onCancel && (
          <Button variant="outline" size="lg" fullWidth className="min-w-0 rounded-xl px-0" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button size="lg" fullWidth className="min-w-0 rounded-xl px-0" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
    </div>
  );
}

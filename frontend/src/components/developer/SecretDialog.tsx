"use client";

import { useState } from "react";
import { EyeIcon, WarningIcon } from "@/components/developer/icons";
import { Button, CheckIcon, Modal } from "@/components/ui";
import type { ApiKeySecret } from "@/lib/developer";

/** A read-only credential box: masked until shown. */
function SecretField({ label, value, revealed }: { label: string; value: string; revealed: boolean }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      <span className="text-body-sm font-medium text-grey-900">{label}</span>
      {/* Shown in full, wrapping, so the whole value can be read and copied. */}
      <p
        className="flex min-h-12 items-center rounded-xl border border-stroke px-4 py-3 font-mono text-body-sm break-all text-grey-900 select-all"
        aria-label={label}
      >
        {revealed ? value : "•".repeat(11)}
      </p>
    </div>
  );
}

/**
 * "API credentials generated": the key ID with Copy, and the secret, hidden
 * until shown, with Copy secret. The only time a secret is ever shown.
 */
export function SecretDialog({
  credentials,
  title = "API credentials generated",
  onDone,
}: {
  credentials: ApiKeySecret;
  title?: string;
  onDone: () => void;
}) {
  const [copied, setCopied] = useState<"key" | "secret" | null>(null);
  const [showSecret, setShowSecret] = useState(false);

  async function copy(which: "key" | "secret") {
    try {
      await navigator.clipboard.writeText(which === "key" ? credentials.key.key_id ?? "" : credentials.secret);
      setCopied(which);
    } catch {
      // Clipboard access can be refused; show the value so it can be selected.
      if (which === "secret") setShowSecret(true);
    }
  }

  return (
    <Modal open title={title} hideTitle>
      <div className="flex w-full flex-col gap-5 text-left">
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-pill bg-primary-500">
            <CheckIcon className="text-white" width={28} height={28} />
          </span>
          <h2 className="text-h3 text-grey-900">{title}</h2>
          <p className="text-body-sm text-grey-900">Your API credentials are ready. Copy and store your secret securely</p>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-body-sm font-medium text-grey-600">{credentials.key.name}</span>
          <span className="w-fit rounded-md bg-info-light px-2 py-0.5 text-xs text-info capitalize">
            {credentials.key.environment}
          </span>
        </div>

        <div className="flex items-end gap-4">
          <SecretField label="API Key" value={credentials.key.key_id ?? ""} revealed />
          <Button variant="outline" className="h-12 shrink-0 rounded-xl px-6" onClick={() => copy("key")}>
            {copied === "key" ? "Copied" : "Copy"}
          </Button>
        </div>

        <div className="flex items-end gap-4">
          <SecretField label="API Secret" value={credentials.secret} revealed={showSecret} />
          <button
            type="button"
            onClick={() => setShowSecret((shown) => !shown)}
            aria-label={showSecret ? "Hide the secret" : "Show the secret"}
            className="flex h-12 w-12 shrink-0 items-center justify-center text-grey-900"
          >
            <EyeIcon open={showSecret} />
          </button>
        </div>
        <Button variant="outline" fullWidth className="-mt-2 rounded-xl" onClick={() => copy("secret")}>
          {copied === "secret" ? "Secret copied" : "Copy secret"}
        </Button>

        <div className="flex flex-col gap-1 rounded-lg bg-grey-50 p-3">
          <p className="flex items-center gap-2 text-body-sm font-medium text-grey-900">
            <WarningIcon className="shrink-0" />
            Save your API secret now
          </p>
          <p className="text-xs leading-4 text-grey-900">
            Your full secret may only be shown once, store it securely before leaving this screen
          </p>
        </div>

        <Button size="lg" fullWidth className="rounded-xl" onClick={onDone}>
          Done
        </Button>
      </div>
    </Modal>
  );
}

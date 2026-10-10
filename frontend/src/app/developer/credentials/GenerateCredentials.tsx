"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChoiceList } from "@/components/developer/ChoiceList";
import { EyeIcon, WarningIcon } from "@/components/developer/icons";
import { useDeveloper } from "@/components/developer/useDeveloper";
import { Button, CheckIcon, Modal } from "@/components/ui";
import { generateCredentials, type Environment, type GeneratedCredentials } from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

const ENVIRONMENTS = [
  { value: "sandbox", label: "Sandbox" },
  { value: "production", label: "Production" },
] as const;

/** A read-only credential box: masked until shown. */
function SecretField({ label, value, revealed }: { label: string; value: string; revealed: boolean }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      <span className="text-body-sm font-medium text-grey-900">{label}</span>
      <p
        className="flex h-12 items-center overflow-hidden rounded-xl border border-stroke px-4 text-body-md text-grey-900 select-all"
        aria-label={label}
      >
        <span className="truncate">{revealed ? value : "•".repeat(11)}</span>
      </p>
    </div>
  );
}

function CredentialsReady({ credentials, onDone }: { credentials: GeneratedCredentials; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  async function copyKey() {
    try {
      await navigator.clipboard.writeText(credentials.key_id);
      setCopied(true);
    } catch {
      // Clipboard access can be refused; the key can still be selected.
    }
  }

  return (
    <Modal open title="API credentials generated" hideTitle>
      <div className="flex w-full flex-col gap-5 text-left">
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-pill bg-primary-500">
            <CheckIcon className="text-white" width={28} height={28} />
          </span>
          <h2 className="text-h3 text-grey-900">API credentials generated</h2>
          <p className="text-body-sm text-grey-900">Your API credentials are ready. Copy and store your secret securely</p>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-body-sm font-medium text-grey-600">Choose Environment</span>
          <span className="w-fit rounded-md bg-info-light px-2 py-0.5 text-xs text-info capitalize">
            {credentials.environment}
          </span>
        </div>

        <div className="flex items-end gap-4">
          <SecretField label="API Key" value={credentials.key_id} revealed={copied} />
          <Button variant="outline" className="h-12 shrink-0 rounded-xl px-6" onClick={copyKey}>
            {copied ? "Copied" : "Copy"}
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

/** "Generate API credentials": pick Sandbox or Production and get a key and secret. */
export function GenerateCredentials() {
  const router = useRouter();
  const { data, error: loadError } = useDeveloper();
  const [environment, setEnvironment] = useState<Environment>("sandbox");
  const [created, setCreated] = useState<GeneratedCredentials | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      setCreated(await generateCredentials(environment));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not generate credentials. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const locked = data !== null && data.kyb_status !== "approved";
  const failure = error ?? loadError ?? (locked ? "Complete and receive approval for KYB to generate your API credentials." : null);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-8 px-6 pt-8 pb-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-body-lg font-semibold text-grey-900">Generate API credentials</h1>
        <p className="text-body-sm text-grey-900">Create credentials to connect your application to our API</p>
      </div>

      <ChoiceList legend="Choose Environment" options={ENVIRONMENTS} value={environment} onChange={setEnvironment} />

      <section className="flex flex-col">
        <h2 className="pb-4 text-body-md text-grey-900">What you&rsquo;ll receive</h2>
        {[
          ["API key", "Identifies your application to the API"],
          ["API secret", "A confidential credential used for authentication, if required by the API"],
        ].map(([title, note]) => (
          <div key={title} className="flex flex-col gap-1 border-b border-stroke py-4">
            <span className="text-body-sm font-medium text-grey-900">{title}</span>
            <span className="text-body-sm text-grey-600">{note}</span>
          </div>
        ))}
        <p className="pt-4 text-xs leading-4 text-grey-900">
          Keep secret credentials private. Never expose them in frontend code or public repositories
        </p>
      </section>

      {failure && (
        <p role="alert" className="text-body-sm text-error">
          {failure}
        </p>
      )}

      <div className="flex flex-col items-center gap-4">
        <Button
          size="lg"
          className="w-60 rounded-xl px-0 text-body-lg font-semibold"
          disabled={!data || locked || busy}
          onClick={generate}
        >
          {busy ? "Generating…" : "Generate credentials"}
        </Button>
        <Link href="/developer">
          <Button variant="outline" size="lg" className="w-36 rounded-xl px-0 text-body-lg font-semibold">
            Cancel
          </Button>
        </Link>
      </div>

      {created && <CredentialsReady credentials={created} onDone={() => router.push("/developer")} />}
    </main>
  );
}

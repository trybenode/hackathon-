"use client";

import { useState, type FormEvent } from "react";
import { AccessPicker } from "@/components/developer/AccessPicker";
import { ChoiceList } from "@/components/developer/ChoiceList";
import { Button, Input, Modal } from "@/components/ui";
import {
  createApiKey,
  maskKeyId,
  updateApiKey,
  type AccessGroup,
  type ApiKey,
  type ApiKeyList,
  type ApiKeySecret,
  type Environment,
} from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

const ENVIRONMENTS = [
  { value: "sandbox", label: "Sandbox" },
  { value: "production", label: "Production" },
] as const;

function message(cause: unknown, fallback: string) {
  return cause instanceof ApiError ? cause.message : fallback;
}

/** "Create API key": name, environment and access; the secret follows once. */
export function CreateKeyDialog({
  groups,
  onClose,
  onCreated,
}: {
  groups: ApiKeyList["access_groups"];
  onClose: () => void;
  onCreated: (created: ApiKeySecret) => void;
}) {
  const [name, setName] = useState("");
  const [environment, setEnvironment] = useState<Environment>("sandbox");
  const [scopes, setScopes] = useState<AccessGroup[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onCreated(await createApiKey(name.trim(), environment, scopes));
    } catch (cause) {
      setError(message(cause, "Could not create the key. Try again."));
      setBusy(false);
    }
  }

  return (
    <Modal open title="Create API key" hideTitle onClose={onClose}>
      <form onSubmit={submit} className="flex w-full flex-col gap-5 text-left">
        <div className="flex flex-col gap-1">
          <h2 className="text-h3 text-grey-900">Create API key</h2>
          <p className="text-body-sm text-grey-600">The secret is shown once, right after this.</p>
        </div>
        <Input
          label="Name"
          placeholder="e.g. Checkout server"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={80}
          required
        />
        <ChoiceList legend="Environment" options={ENVIRONMENTS} value={environment} onChange={setEnvironment} />
        <AccessPicker groups={groups} value={scopes} onChange={setScopes} />
        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}
        <div className="flex gap-3">
          <Button type="button" variant="outline" fullWidth className="min-w-0 rounded-xl px-0" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" fullWidth className="min-w-0 rounded-xl px-0" disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create key"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/** "Edit key": rename and change access. The environment never changes. */
export function EditKeyDialog({
  apiKey,
  groups,
  onClose,
  onSaved,
}: {
  apiKey: ApiKey;
  groups: ApiKeyList["access_groups"];
  onClose: () => void;
  onSaved: (saved: ApiKey) => void;
}) {
  const [name, setName] = useState(apiKey.name);
  const [scopes, setScopes] = useState<AccessGroup[] | null>(apiKey.scopes);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSaved(await updateApiKey(apiKey.id, name.trim(), scopes));
    } catch (cause) {
      setError(message(cause, "Could not save the key. Try again."));
      setBusy(false);
    }
  }

  return (
    <Modal open title="Edit API key" hideTitle onClose={onClose}>
      <form onSubmit={submit} className="flex w-full flex-col gap-5 text-left">
        <div className="flex flex-col gap-1">
          <h2 className="text-h3 text-grey-900">Edit API key</h2>
          <p className="font-mono text-body-sm break-all text-grey-600">{apiKey.key_id ? maskKeyId(apiKey.key_id) : ""}</p>
        </div>
        <Input label="Name" value={name} onChange={(event) => setName(event.target.value)} maxLength={80} required />
        <div className="flex flex-col gap-1">
          <span className="text-body-sm font-medium text-grey-600">Environment</span>
          <span className="text-body-md text-grey-900 capitalize">{apiKey.environment}</span>
          <span className="text-xs leading-4 text-grey-600">Fixed when the key was made.</span>
        </div>
        <AccessPicker groups={groups} value={scopes} onChange={setScopes} />
        <p className="text-xs leading-4 text-grey-600">
          {apiKey.can_attest
            ? "Approved to attest: records this key imports count as verified."
            : "Imported records count as verified only after we approve your platform to attest."}
        </p>
        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}
        <div className="flex gap-3">
          <Button type="button" variant="outline" fullWidth className="min-w-0 rounded-xl px-0" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" fullWidth className="min-w-0 rounded-xl px-0" disabled={busy || !name.trim()}>
            {busy ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/** A yes/no question before something that cannot be undone. */
export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  danger = false,
  onConfirm,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (cause) {
      setError(message(cause, "That did not work. Try again."));
      setBusy(false);
    }
  }

  return (
    <Modal open title={title} hideTitle onClose={onClose}>
      <div className="flex w-full flex-col gap-4 text-left">
        <h2 className="text-h3 text-grey-900">{title}</h2>
        <div className="text-body-sm text-grey-900">{children}</div>
        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}
        <div className="flex gap-3 pt-2">
          <Button variant="outline" fullWidth className="min-w-0 rounded-xl px-0" onClick={onClose}>
            Cancel
          </Button>
          <Button
            fullWidth
            variant={danger ? "ghost" : "fill"}
            className={danger ? "min-w-0 rounded-xl bg-error px-0 text-white hover:bg-error/90" : "min-w-0 rounded-xl px-0"}
            disabled={busy}
            onClick={confirm}
          >
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

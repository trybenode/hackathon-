"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AccessChips } from "@/components/developer/AccessPicker";
import { useDeveloper } from "@/components/developer/DeveloperContext";
import { CopyIcon, KeyIcon } from "@/components/developer/icons";
import { ConfirmDialog, CreateKeyDialog, EditKeyDialog } from "@/components/developer/KeyDialogs";
import { PageHeader } from "@/components/developer/PageHeader";
import { SecretDialog } from "@/components/developer/SecretDialog";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import {
  listApiKeys,
  maskKeyId,
  revokeApiKey,
  rotateApiKey,
  type ApiKey,
  type ApiKeyList,
  type ApiKeySecret,
} from "@/lib/developer";
import { formatRelative } from "@/lib/format";
import { ApiError } from "@/lib/guarantor";

type Open =
  | { kind: "create" }
  | { kind: "edit"; key: ApiKey }
  | { kind: "rotate"; key: ApiKey }
  | { kind: "revoke"; key: ApiKey }
  | { kind: "secret"; value: ApiKeySecret; title: string }
  | null;

function EnvironmentBadge({ environment }: { environment: ApiKey["environment"] }) {
  return (
    <span
      className={cn(
        "rounded-md px-2 py-0.5 text-xs capitalize",
        environment === "sandbox" ? "bg-info-light text-info" : "bg-success-light text-grey-900",
      )}
    >
      {environment}
    </span>
  );
}

function KeyIdCopy({ keyId }: { keyId: string | null }) {
  const [copied, setCopied] = useState(false);
  if (!keyId) return <span className="text-body-sm text-grey-600">—</span>;
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(keyId);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // The id stays on screen to select by hand.
        }
      }}
      className="flex max-w-full min-w-0 items-center gap-1.5 font-mono text-xs text-grey-900 hover:text-primary-500"
      aria-label={`Copy key ID ${keyId}`}
    >
      <span className="truncate">{maskKeyId(keyId)}</span>
      <CopyIcon className={cn("shrink-0", copied ? "text-success" : "text-grey-600")} />
    </button>
  );
}

function Actions({ onEdit, onRotate, onRevoke }: { onEdit: () => void; onRotate: () => void; onRevoke: () => void }) {
  return (
    <span className="flex flex-wrap items-center gap-x-4 gap-y-2 text-body-sm font-medium whitespace-nowrap">
      <button type="button" onClick={onEdit} className="text-grey-900 hover:text-primary-500">
        Edit
      </button>
      <button type="button" onClick={onRotate} className="text-grey-900 hover:text-primary-500">
        Rotate
      </button>
      <button type="button" onClick={onRevoke} className="text-error hover:underline">
        Revoke
      </button>
    </span>
  );
}

/** The key's access, with its attest status when it has one. */
function KeyAccess({ apiKey, groups }: { apiKey: ApiKey; groups: ApiKeyList["access_groups"] }) {
  return (
    <span className="flex flex-col gap-1.5">
      <AccessChips groups={groups} scopes={apiKey.scopes} />
      {(apiKey.can_attest || apiKey.attest_requested) && (
        <span className="w-fit rounded-md bg-warning-light px-2 py-0.5 text-xs text-grey-900">
          {apiKey.can_attest ? "Attests" : "Attest requested"}
        </span>
      )}
    </span>
  );
}

function lastUsed(key: ApiKey) {
  return key.last_used_at ? formatRelative(key.last_used_at) : "Never";
}

/** "API keys": every active key, its access, and what can be done with it. */
export function ApiKeys() {
  const { data: account, reload: reloadAccount } = useDeveloper();
  const approved = account?.kyb_status === "approved";
  const [list, setList] = useState<ApiKeyList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Open>(null);

  const load = useCallback(() => {
    listApiKeys()
      .then((loaded) => {
        setList(loaded);
        setError(null);
      })
      .catch((cause) => setError(cause instanceof ApiError ? cause.message : "Could not load your API keys."));
  }, []);

  useEffect(() => {
    if (approved) load();
  }, [approved, load]);

  function refresh() {
    load();
    // The dashboard counts active keys.
    reloadAccount();
  }

  const keys = list?.items ?? [];
  const groups = list?.access_groups ?? [];

  return (
    <div className="flex flex-col">
      <PageHeader
        title="API keys"
        description="Create and manage the credentials your applications use. A secret is shown only once."
        actions={
          approved && (
            <Button className="rounded-lg px-6 font-semibold" disabled={!list} onClick={() => setOpen({ kind: "create" })}>
              Create API key
            </Button>
          )
        }
      />

      {account && !approved && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-stroke px-6 py-12 text-center">
          <KeyIcon className="text-grey-600" width={28} height={28} />
          <p className="text-body-md text-grey-900">API keys unlock after KYB approval</p>
          <p className="max-w-md text-body-sm text-grey-600">
            Complete and receive approval for KYB to generate your API credentials.
          </p>
          <Link href="/developer/verify">
            <Button variant="outline" className="mt-2 rounded-lg px-8 font-semibold">
              Go to verification
            </Button>
          </Link>
        </div>
      )}

      {error && (
        <p role="alert" className="pb-4 text-body-sm text-error">
          {error}
        </p>
      )}

      {approved && list && keys.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-stroke px-6 py-12 text-center">
          <KeyIcon className="text-grey-600" width={28} height={28} />
          <p className="text-body-md text-grey-900">No API keys yet</p>
          <p className="max-w-md text-body-sm text-grey-600">
            Start with a Sandbox key: it works against the demo workers in the Docs, so you can try every call first.
          </p>
          <Button className="mt-2 rounded-lg px-8 font-semibold" onClick={() => setOpen({ kind: "create" })}>
            Create API key
          </Button>
        </div>
      )}

      {approved && keys.length > 0 && (
        <>
          {/* Desktop: a table. */}
          <div className="hidden overflow-hidden rounded-xl border border-stroke lg:block">
            <table className="w-full table-fixed text-left">
              <thead className="bg-grey-50 text-xs text-grey-600">
                <tr>
                  <th className="w-[19%] px-4 py-3 font-medium">Name</th>
                  <th className="w-[24%] px-4 py-3 font-medium">Key ID</th>
                  <th className="w-[18%] px-4 py-3 font-medium">Access</th>
                  <th className="w-[11%] px-4 py-3 font-medium">Last used</th>
                  <th className="w-[8%] px-4 py-3 font-medium whitespace-nowrap">Calls · 14d</th>
                  <th className="w-[20%] px-4 py-3 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr key={key.id} className="border-t border-stroke align-top">
                    <td className="px-4 py-4">
                      <span className="flex flex-col gap-1.5">
                        <span className="truncate text-body-sm font-medium text-grey-900">{key.name}</span>
                        <span className="flex items-center gap-2">
                          <EnvironmentBadge environment={key.environment} />
                          <span className="text-xs text-grey-600">Created {formatRelative(key.created_at)}</span>
                        </span>
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <KeyIdCopy keyId={key.key_id} />
                    </td>
                    <td className="px-4 py-4">
                      <KeyAccess apiKey={key} groups={groups} />
                    </td>
                    <td className="px-4 py-4 text-body-sm text-grey-900">{lastUsed(key)}</td>
                    <td className="px-4 py-4 text-body-sm text-grey-900">{key.recent_calls}</td>
                    <td className="px-4 py-4">
                      <Actions
                        onEdit={() => setOpen({ kind: "edit", key })}
                        onRotate={() => setOpen({ kind: "rotate", key })}
                        onRevoke={() => setOpen({ kind: "revoke", key })}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Phone and tablet: cards. */}
          <ul className="flex flex-col gap-4 lg:hidden">
            {keys.map((key) => (
              <li key={key.id} className="flex flex-col gap-3 rounded-xl border border-stroke p-4">
                <div className="flex items-start justify-between gap-3">
                  <span className="min-w-0 truncate text-body-md font-medium text-grey-900">{key.name}</span>
                  <EnvironmentBadge environment={key.environment} />
                </div>
                <KeyIdCopy keyId={key.key_id} />
                <KeyAccess apiKey={key} groups={groups} />
                <p className="text-xs text-grey-600">
                  Last used {lastUsed(key).toLowerCase()} · {key.recent_calls} calls in 14 days
                </p>
                <div className="border-t border-stroke pt-3">
                  <Actions
                    onEdit={() => setOpen({ kind: "edit", key })}
                    onRotate={() => setOpen({ kind: "rotate", key })}
                    onRevoke={() => setOpen({ kind: "revoke", key })}
                  />
                </div>
              </li>
            ))}
          </ul>

          <p className="pt-4 text-xs text-grey-600">
            Up to {list?.max_active_per_environment} active keys per environment. Revoked keys are removed from this list.
          </p>
        </>
      )}

      {open?.kind === "create" && (
        <CreateKeyDialog
          groups={groups}
          onClose={() => setOpen(null)}
          onCreated={(created) => {
            setOpen({ kind: "secret", value: created, title: "API credentials generated" });
            refresh();
          }}
        />
      )}
      {open?.kind === "edit" && (
        <EditKeyDialog
          apiKey={open.key}
          groups={groups}
          onClose={() => setOpen(null)}
          onSaved={() => {
            setOpen(null);
            refresh();
          }}
          onAttestRequested={load}
        />
      )}
      {open?.kind === "rotate" && (
        <ConfirmDialog
          title="Rotate secret?"
          confirmLabel="Rotate secret"
          onClose={() => setOpen(null)}
          onConfirm={async () => {
            const rotated = await rotateApiKey(open.key.id);
            setOpen({ kind: "secret", value: rotated, title: "New secret generated" });
            refresh();
          }}
        >
          <p>
            <strong>{open.key.name}</strong> gets a new secret. The current secret stops working straight away, so
            update your application with the new one. The key ID and its access stay the same.
          </p>
        </ConfirmDialog>
      )}
      {open?.kind === "revoke" && (
        <ConfirmDialog
          title="Revoke this key?"
          confirmLabel="Revoke key"
          danger
          onClose={() => setOpen(null)}
          onConfirm={async () => {
            await revokeApiKey(open.key.id);
            setOpen(null);
            refresh();
          }}
        >
          <p>
            <strong>{open.key.name}</strong> stops working immediately and is removed from this list. This can&rsquo;t
            be undone.
          </p>
        </ConfirmDialog>
      )}
      {open?.kind === "secret" && (
        <SecretDialog credentials={open.value} title={open.title} onDone={() => setOpen(null)} />
      )}
    </div>
  );
}

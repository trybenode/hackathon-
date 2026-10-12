"use client";

import { useState } from "react";
import { useDeveloper } from "@/components/developer/DeveloperContext";
import { CopyIcon } from "@/components/developer/icons";
import { PageHeader } from "@/components/developer/PageHeader";
import { apiBaseUrl } from "@/lib/api";
import { cn } from "@/lib/cn";

function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  async function copy(id: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // The text stays on screen to select by hand.
    }
  }
  return { copied, copy };
}

function CodeBlock({ id, code, copied, onCopy }: { id: string; code: string; copied: boolean; onCopy: (id: string, text: string) => void }) {
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-lg bg-grey-900 p-4 pr-12 font-mono text-xs leading-5 text-white">
        <code>{code}</code>
      </pre>
      <button
        type="button"
        onClick={() => onCopy(id, code)}
        aria-label="Copy code"
        className={cn("absolute top-3 right-3", copied ? "text-success-mid" : "text-grey-400 hover:text-white")}
      >
        <CopyIcon />
      </button>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-body-lg font-semibold text-grey-900">{title}</h2>
      {children}
    </section>
  );
}

const ACCESS = [
  { group: "Trust & workers", endpoints: ["POST /platform/worker-links", "POST /trust/query"] },
  { group: "Work history", endpoints: ["GET /platform/workers/{external_id}/history", "POST /platform/workers/{external_id}/history/import"] },
  { group: "Guarantees", endpoints: ["GET /guarantor-instruments", "POST /guarantor-instruments", "POST /guarantor-instruments/{id}/send | trigger | resolve | revoke"] },
  { group: "Scoring settings", endpoints: ["GET /platform/scoring-config", "PUT | DELETE /platform/scoring-config/{platform_type}"] },
];

/** "Docs": how to call the API, the sandbox demo workers, and what each access group allows. */
export function DeveloperDocs() {
  const { data } = useDeveloper();
  const { copied, copy } = useCopy();
  const ada = data?.sandbox_workers[0]?.consent_token ?? "sandbox-consent-ada-demo-worker-token";

  const steps = [
    {
      id: "link",
      title: "1. Link a demo worker",
      note: "Use any id from your own system. The response carries the worker_id.",
      code: `curl -X POST "${apiBaseUrl}/platform/worker-links" \\
  -H "X-API-Key: $SECRET" -H "Content-Type: application/json" \\
  -d '{"external_worker_id": "user-42", "consent_token": "${ada}"}'`,
    },
    {
      id: "trust",
      title: "2. Ask for a trust assessment",
      note: "Returns the decision, confidence and band, plus what has been verified about the worker.",
      code: `curl -X POST "${apiBaseUrl}/trust/query" \\
  -H "X-API-Key: $SECRET" -H "Content-Type: application/json" \\
  -d '{"worker_id": "<worker_id>", "platform_type": "generic", "job_context": {"job_type": "cleaning", "value_band": "low"}}'`,
    },
    {
      id: "history",
      title: "3. Read the worker's history",
      note: "Paged, newest first, with where each record came from.",
      code: `curl "${apiBaseUrl}/platform/workers/user-42/history" -H "X-API-Key: $SECRET"`,
    },
  ];

  return (
    <div className="flex max-w-4xl flex-col gap-10">
      <PageHeader title="Docs" description="Connect your application to the trust API" />

      <Section title="Authentication">
        <p className="text-body-sm text-grey-900">
          Send your API secret in the <code className="rounded bg-grey-50 px-1 font-mono text-xs">X-API-Key</code> header on
          every request. Keep it on your server: never in frontend code or a public repository. The key ID
          (<code className="rounded bg-grey-50 px-1 font-mono text-xs">pk_…</code>) only identifies the key and is safe to share.
        </p>
        <div className="flex flex-col gap-1 rounded-lg border border-stroke p-4">
          <span className="text-xs text-grey-600">Base URL</span>
          <span className="font-mono text-body-sm break-all text-grey-900">{apiBaseUrl}</span>
        </div>
      </Section>

      <Section title="Sandbox demo workers">
        <p className="text-body-sm text-grey-900">
          Sandbox keys reach only these demo workers, and production keys never do. Each history is fixed to land in one
          band, so the same call always gets the same answer. Changes you send in the sandbox are answered but never kept.
        </p>
        <div className="overflow-x-auto rounded-xl border border-stroke">
          <table className="w-full min-w-[640px] text-left">
            <thead className="bg-grey-50 text-xs text-grey-600">
              <tr>
                <th className="px-4 py-3 font-medium">Worker</th>
                <th className="px-4 py-3 font-medium">Band</th>
                <th className="px-4 py-3 font-medium">Guarantor</th>
                <th className="px-4 py-3 font-medium">Consent token</th>
              </tr>
            </thead>
            <tbody>
              {(data?.sandbox_workers ?? []).map((worker) => (
                <tr key={worker.consent_token} className="border-t border-stroke">
                  <td className="px-4 py-3">
                    <span className="flex flex-col">
                      <span className="text-body-sm font-medium text-grey-900">{worker.name}</span>
                      <span className="text-xs text-grey-600">{worker.role}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3 text-body-sm text-grey-900">{worker.band}</td>
                  <td className="px-4 py-3 text-body-sm text-grey-900 capitalize">{worker.guarantor ?? "None"}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => copy(worker.consent_token, worker.consent_token)}
                      className="flex items-center gap-1.5 font-mono text-xs text-grey-900 hover:text-primary-500"
                    >
                      {worker.consent_token}
                      <CopyIcon className={copied === worker.consent_token ? "text-success" : "text-grey-600"} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Quickstart">
        {steps.map((step) => (
          <div key={step.id} className="flex flex-col gap-2">
            <h3 className="text-body-md font-medium text-grey-900">{step.title}</h3>
            <p className="text-body-sm text-grey-600">{step.note}</p>
            <CodeBlock id={step.id} code={step.code} copied={copied === step.id} onCopy={copy} />
          </div>
        ))}
      </Section>

      <Section title="Access groups">
        <p className="text-body-sm text-grey-900">
          Give each key only the access it needs; full-access keys also get features added later. A worker&rsquo;s
          approval always applies on top: access never reaches further than what workers approved.
        </p>
        <div className="overflow-hidden rounded-xl border border-stroke">
          {ACCESS.map((row, index) => (
            <div key={row.group} className={cn("flex flex-col gap-2 p-4 sm:flex-row sm:gap-6", index > 0 && "border-t border-stroke")}>
              <span className="w-40 shrink-0 text-body-sm font-medium text-grey-900">{row.group}</span>
              <span className="flex flex-col gap-1">
                {row.endpoints.map((endpoint) => (
                  <code key={endpoint} className="font-mono text-xs break-all text-grey-800">
                    {endpoint}
                  </code>
                ))}
              </span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Errors">
        <p className="text-body-sm text-grey-900">
          Errors return a <code className="rounded bg-grey-50 px-1 font-mono text-xs">code</code> and a readable{" "}
          <code className="rounded bg-grey-50 px-1 font-mono text-xs">detail</code>. The ones you&rsquo;ll meet first:{" "}
          <code className="font-mono text-xs">401</code> (missing or wrong secret),{" "}
          <code className="font-mono text-xs">SCOPE_REQUIRED</code> (the key lacks that access),{" "}
          <code className="font-mono text-xs">CONSENT_REQUIRED</code> (the worker has not approved you) and{" "}
          <code className="font-mono text-xs">ENVIRONMENT_MISMATCH</code> (a sandbox key with a real worker, or the other way round).
        </p>
      </Section>
    </div>
  );
}

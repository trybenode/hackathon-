"use client";
import { useState } from "react";
import { Button } from "@/components/ui";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { ApiFailure, errorMessage } from "@/lib/portability";
import { getWorkerRecord, importCredentials } from "@/lib/workerRecord";

export function ImportRecordDialog({ workerId, open, onClose, onImported }: { workerId: string; open: boolean; onClose: () => void; onImported: () => Promise<void> }) {
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  async function submit() {
    setBusy(true); setError(""); setResult("");
    try {
      let token: unknown = input.trim();
      if (typeof token === "string" && token.startsWith("{")) token = (JSON.parse(token) as { credential_token?: unknown }).credential_token;
      if (typeof token !== "string" || !token || token.length > 1_000_000) throw new Error("Provide a JSON export containing credential_token, or paste a signed token up to 1 MB.");
      if (uncertain) await getWorkerRecord();
      // Replaying the same signed bundle is deduplicated by the server.
      const imported = await importCredentials(workerId, token);
      setUncertain(false);
      setResult(imported.imported_outcomes ? `${imported.imported_outcomes} new records imported. Current band: ${imported.new_band}.` : "No new records: these records are already present. Your record is refreshed.");
      await onImported();
    } catch (e) {
      setError(e instanceof SyntaxError ? "The JSON file is malformed. Check the export and try again." : errorMessage(e));
      setUncertain(e instanceof ApiFailure && (e.status === 0 || e.status >= 500));
    } finally { setBusy(false); }
  }
  return <WorkerDialog open={open} onClose={() => { if (!busy) onClose(); }} label="Import work record"><div className="flex flex-col gap-4"><h2 className="text-body-lg font-semibold">Import work record</h2><p className="text-body-sm text-grey-600">Import a signed JSON export or token for your worker account. Source labels are preserved; self-declared history stays separate from verified evidence.</p>
    <label className="text-body-sm">JSON export<input type="file" accept="application/json,.json" disabled={busy || uncertain} className="mt-2 block w-full" onChange={async e => { const file = e.target.files?.[0]; if (!file) return; try { if (file.size > 1_500_000) throw new Error("Choose a JSON export smaller than 1.5 MB."); setInput(await file.text()); setError(""); setResult(""); } catch (cause) { setError(errorMessage(cause)); } }} /></label>
    <label className="text-body-sm">Or paste the signed token<textarea value={input} disabled={busy || uncertain} onChange={e => { setInput(e.target.value); setResult(""); }} maxLength={1_500_000} rows={5} className="mt-2 w-full rounded-lg border border-stroke p-3" /></label>
    {error && <p role="alert" className="text-body-sm text-error">{error}</p>}{result && <p role="status" className="text-body-sm text-success">{result}</p>}
    <Button disabled={busy || !input.trim()} onClick={submit}>{busy ? "Checking import…" : uncertain ? "Check record and retry same import" : "Import signed record"}</Button><Button variant="outline" disabled={busy} onClick={onClose}>Close</Button></div></WorkerDialog>;
}

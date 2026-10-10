"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { EvidenceSummary } from "@/components/worker/EvidenceSummary";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { useGrantCreation } from "@/components/worker/useGrantCreation";
import { dateLabel, errorMessage, featureRequest, type Grant, type Page, type VerificationSummary } from "@/lib/portability";

export function ShareVerification({ summary, refresh }: { summary: VerificationSummary; refresh: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [grants, setGrants] = useState<Page<Grant> | null>(null);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 60000); return () => clearInterval(timer); }, []);
  const generating = useRef(false);
  const [preparing, setPreparing] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [link, setLink] = useState("");
  const creation = useGrantCreation("/me/worker/shares");
  useEffect(() => {
    const controller = new AbortController();
    featureRequest<Page<Grant>>(`/me/worker/shares?page=${page}`, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setGrants(value); }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [page, revision, creation.issued?.id, creation.lost?.id]);
  async function generate() {
    if (generating.current) return;
    generating.current = true; setPreparing(true); setError("");
    try { await refresh(); const grant = await creation.create(); if (grant?.token) setLink(`${window.location.origin}/verify/${encodeURIComponent(grant.token)}`); }
    finally { generating.current = false; setPreparing(false); }
  }
  async function revoke(id: string) {
    setRevoking(true); setError("");
    try { await featureRequest(`/me/worker/shares/${id}`, { method: "DELETE" }); if (creation.issued?.id === id) { creation.clearIssued(); setLink(""); } setRevision(value => value + 1); }
    catch (e) { setError(errorMessage(e)); }
    finally { setRevoking(false); }
  }
  const busy = preparing || revoking || creation.busy;
  return <section className="flex flex-col gap-4 rounded-xl border border-stroke p-5"><h2 className="text-body-lg font-semibold">Share verification</h2><p className="text-body-sm text-grey-600">Share a live standard summary for seven days. Client details, identity documents, credential tokens and detailed allegations are excluded.</p><Button variant="outline" onClick={() => { setOpen(true); void refresh(); }}>Preview shared summary</Button>
    {(error || creation.error) && <p role="alert" className="text-body-sm text-error">{error || creation.error}</p>}
    {creation.uncertain && <Button variant="outline" disabled={busy} onClick={creation.check}>Check whether link creation completed</Button>}
    {creation.lost && <div className="rounded-lg border border-stroke p-3 text-body-sm"><p>Link creation completed, but its secret was not received. Revoke this link before generating a replacement.</p><Button variant="outline" disabled={busy} onClick={async () => { await creation.revokeLost(); setRevision(value => value + 1); }}>Revoke unavailable link</Button></div>}
    {creation.issued?.token && <div className="flex flex-col gap-3"><label className="text-body-sm">Verification link<input readOnly value={link} className="mt-2 w-full rounded-lg border border-stroke p-3" /></label><p className="text-body-sm">Expires {dateLabel(creation.issued.expires_at)}. This link is shown once.</p><div className="flex flex-wrap gap-3"><Button variant="outline" onClick={async () => { try { await navigator.clipboard.writeText(link); setError(""); } catch { setError("Copy the link from the field above."); } }}>Copy link</Button><a href={`https://wa.me/?text=${encodeURIComponent(`My work verification: ${link}`)}`} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-stroke px-4 py-3 text-body-sm">Share on WhatsApp</a></div></div>}
    {grants?.items.map(grant => <div key={grant.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-stroke pt-3 text-body-sm"><span>{grant.revoked_at ? "Revoked" : new Date(grant.expires_at).getTime() <= clock ? "Expired" : "Active"} · Expires {dateLabel(grant.expires_at)}</span><Button size="sm" variant="outline" disabled={busy || !!grant.revoked_at} onClick={() => revoke(grant.id)}>Revoke</Button></div>)}
    <Button variant="outline" disabled={busy} onClick={() => { setError(""); setRevision(value => value + 1); }}>Refresh links</Button>
    {grants && grants.pages > 1 && <nav aria-label="Share link pages" className="flex items-center justify-between"><Button variant="outline" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</Button><span>{page} / {grants.pages}</span><Button variant="outline" disabled={page >= grants.pages} onClick={() => setPage(value => value + 1)}>Next</Button></nav>}
    <WorkerDialog open={open} onClose={() => { if (!busy) setOpen(false); }} label="Preview verification summary"><div className="flex flex-col gap-4"><h2 className="text-body-lg font-semibold">Preview shared summary</h2><EvidenceSummary record={summary} /><p className="text-body-sm text-grey-600">The link shows current evidence when opened. Detailed access needs a separate named-platform approval.</p><Button disabled={busy || creation.uncertain || !!creation.lost} onClick={async () => { await generate(); setOpen(false); }}>{busy ? "Generating…" : "Generate seven-day link"}</Button><Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>Close</Button></div></WorkerDialog>
  </section>;
}

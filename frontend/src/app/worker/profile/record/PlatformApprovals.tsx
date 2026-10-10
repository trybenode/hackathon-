"use client";
import { useEffect, useState } from "react";
import { useGrantCreation } from "@/components/worker/useGrantCreation";
import { Button } from "@/components/ui";
import { dateLabel, errorMessage, featureRequest, type Grant, type Page } from "@/lib/portability";

type Platform = { id: string; name: string };
export function PlatformApprovals() {
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [catalogPage, setCatalogPage] = useState(1);
  const [catalogPages, setCatalogPages] = useState(1);
  const [platformId, setPlatformId] = useState("");
  const [read, setRead] = useState(true);
  const [ingest, setIngest] = useState(false);
  const [grants, setGrants] = useState<Page<Grant> | null>(null);
  const creation = useGrantCreation("/me/worker/platform-grants");
  const issued = creation.issued;
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 60000); return () => clearInterval(timer); }, []);
  const [working, setBusy] = useState(false);
  const busy = working || creation.busy;
  const locked = busy || creation.uncertain || !!creation.lost;
  useEffect(() => {
    let active = true;
    Promise.all([featureRequest<Page<Platform>>("/me/worker/platforms?size=100"), featureRequest<Page<Grant>>(`/me/worker/platform-grants?page=${page}`)]).then(([options, approvals]) => {
      if (active) { setPlatforms(prev => [...new Map([...prev, ...options.items].map(p => [p.id, p])).values()]); setCatalogPages(options.pages); setGrants(approvals); setError(""); }
    }).catch(e => { if (active) setError(errorMessage(e)); });
    return () => { active = false; };
  }, [page, revision, creation.issued?.id, creation.lost?.id]);
  async function morePlatforms() {
    setBusy(true);
    try {
      const catalog = await featureRequest<Page<Platform>>(`/me/worker/platforms?size=100&page=${catalogPage + 1}`);
      setPlatforms(prev => [...new Map([...prev, ...catalog.items].map(p => [p.id, p])).values()]); setCatalogPage(catalog.page);
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function approve() {
    setError("");
    await creation.create({ organization_id: platformId, permissions: [...(read ? ["read_history"] : []), ...(ingest ? ["import_history"] : [])] });
    setRevision(v => v + 1);
  }
  async function revoke(id: string) {
    setBusy(true); setError("");
    try { await featureRequest(`/me/worker/platform-grants/${id}`, { method: "DELETE" }); if (issued?.id === id) creation.clearIssued(); setRevision(v => v + 1); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  return <section className="flex flex-col gap-4 rounded-xl border border-stroke p-5"><h2 className="text-body-lg font-semibold">Approve a platform</h2><p className="text-body-sm text-grey-600">Choose who can access your detailed history. Approval lasts seven days. Revoking it stops future access, but cannot recall records already downloaded.</p>
    {(error || creation.error) && <div role="alert"><p className="text-error">{error || creation.error}</p><Button variant="outline" onClick={() => setRevision(v => v + 1)}>Refresh approvals</Button></div>}
    <label className="text-body-sm">Platform<select value={platformId} disabled={locked} onChange={e => { setPlatformId(e.target.value); creation.clearIssued(); }} className="mt-2 min-h-12 w-full rounded-lg border border-stroke p-3"><option value="">Select a named platform</option>{platforms.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    {catalogPage < catalogPages && <Button variant="outline" disabled={busy} onClick={morePlatforms}>Load more platforms</Button>}
    {!platforms.length && !error && <p className="text-body-sm text-grey-600">No integrating platforms are available yet.</p>}
    <label className="flex items-start gap-3 text-body-sm"><input type="checkbox" checked={read} disabled={locked} onChange={e => setRead(e.target.checked)} className="mt-1" />Let this platform read my detailed work history and assessment.</label>
    <label className="flex items-start gap-3 text-body-sm"><input type="checkbox" checked={ingest} disabled={locked} onChange={e => setIngest(e.target.checked)} className="mt-1" />Let this platform add historical work evidence, with its source clearly recorded.</label>
    <Button disabled={locked || !platformId || (!read && !ingest)} onClick={approve}>{busy ? "Working…" : "Approve selected platform"}</Button>
    {creation.uncertain && <Button variant="outline" disabled={busy} onClick={creation.check}>Check whether approval completed</Button>}
    {creation.lost && <div className="text-body-sm"><p>Approval completed, but its token was not received. Revoke it before creating a replacement.</p><Button variant="outline" disabled={busy} onClick={async () => { await creation.revokeLost(); setRevision(v => v + 1); }}>Revoke unavailable approval</Button></div>}
    {issued?.token && <label className="text-body-sm">Send this approval token privately to {issued.organization_name}.<textarea readOnly value={issued.token} rows={2} className="mt-2 w-full rounded-lg border border-stroke p-3 break-all" /><span className="mt-2 block text-grey-600">Shown once. Expires {dateLabel(issued.expires_at)}.</span></label>}
    {grants?.items.map(g => <div key={g.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-stroke pt-3 text-body-sm"><div><p>{g.organization_name}</p><p className="text-grey-600">{g.revoked_at ? "Revoked" : new Date(g.expires_at).getTime() <= clock ? `Expired ${dateLabel(g.expires_at)}` : `Expires ${dateLabel(g.expires_at)}`} · {g.permissions?.map(permission => permission === "read_history" ? "Read history and assessment" : "Add historical evidence").join(" · ")}</p></div><Button size="sm" variant="outline" disabled={busy || !!g.revoked_at} onClick={() => revoke(g.id)}>Revoke</Button></div>)}
    {grants && grants.pages > 1 && <div className="flex justify-between"><Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button><span>{page} / {grants.pages}</span><Button size="sm" variant="outline" disabled={page >= grants.pages} onClick={() => setPage(p => p + 1)}>Next</Button></div>}
  </section>;
}

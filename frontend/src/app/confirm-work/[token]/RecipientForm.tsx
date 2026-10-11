"use client";
import { historyError, uncertainFailure } from "@/lib/historyErrors";
import Link from "next/link";
import { ClarificationThread } from "@/components/history/ClarificationThread";
import { LanguageSelector, useLanguage } from "@/components/history/LanguageProvider";
import { useCallback, useEffect, useRef, useState } from "react";
import { featureRequest } from "@/lib/portability";
import type { Recipient, Receipt } from "@/lib/history";

/** A link never proves customer identity; verify contact or match the existing account. */
export function RecipientForm({ token }: { token: string }) {
  const { language, t } = useLanguage();
  const base = `/history-confirmations/${encodeURIComponent(token)}`;
  const [data, setData] = useState<Recipient | null>(null);
  const [translation, setTranslation] = useState("");
  const [code, setCode] = useState("");
  const [debug, setDebug] = useState("");
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const payloadRef = useRef<{ decision: string; declares_customer: boolean; consent: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [decision, setDecision] = useState("confirmed");
  const [declares, setDeclares] = useState(false);
  const [consent, setConsent] = useState(false);
  const operation = useRef<string | null>(null);
  const load = useCallback(async (signal?: AbortSignal) => {
    const value = await featureRequest<Recipient>(base, { signal });
    if (!signal?.aborted) setData(value);
  }, [base]);
  useEffect(() => { const c = new AbortController(); void featureRequest<Recipient>(base, { signal: c.signal }).then(value => { if (!c.signal.aborted) setData(value); }).catch(e => { if (!c.signal.aborted) setError(historyError(e, t)); }); return () => c.abort(); }, [base, t]);
  async function action(fn: () => Promise<unknown>) { setBusy(true); setError(""); try { await fn(); await load(); } catch (e) { setError(historyError(e, t)); } finally { setBusy(false); } }
  async function respond() {
    operation.current ??= crypto.randomUUID();
    payloadRef.current ??= { decision, declares_customer: declares, consent };
    try {
      const receipt = await featureRequest<Receipt>(`${base}/response`, { method: "POST", headers: { "Idempotency-Key": operation.current }, body: JSON.stringify(payloadRef.current) });
      setUncertain(false);
      setData(d => d ? { ...d, response: receipt } : d);
    } catch (e) {
      // Reconcile the receipt before retrying; the decision remains in memory.
      const unknown = uncertainFailure(e); setUncertain(unknown); if (!unknown) { payloadRef.current = null; operation.current = null; }
      await load().catch(() => undefined);
      throw e;
    }
  }
  return <main className="history-journey mx-auto flex w-full max-w-xl flex-col gap-5 p-5"><LanguageSelector /><h1 className="text-h3 font-semibold">{t("confirmTitle")}</h1><p>{t("privacy")}</p>
    {error && <p role="alert">{error}</p>}{!data && <button onClick={() => void action(() => load())}>{t("retry")}</button>}
    {data?.access === "account_required" && <><p>{t("accountRequired")}</p><Link href={`/sign-in?next=${encodeURIComponent(`/confirm-work/${token}`)}`}>{t("signIn")}</Link><button onClick={() => void action(() => load())}>{t("checkAccount")}</button></>}
    {data?.access === "contact_required" && <section className="flex flex-col gap-3"><p>{t("contactRequired")} {data.masked_phone}. {t("scoreUnchanged")}</p><button disabled={busy} onClick={() => void action(async () => { const r = await featureRequest<{ debug_code: string | null; sandbox: boolean }>(`${base}/challenge`, { method: "POST" }); setDebug(r.debug_code || ""); })}>{t("sendCode")}</button>{debug && <p>{t("sandbox")}: {debug}. {t("noSms")}</p>}<label>{t("code")}<input autoComplete="one-time-code" inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value)} className="block w-full rounded border p-2" /></label><button disabled={busy || !/^[0-9]{6}$/.test(code)} onClick={() => void action(() => featureRequest(`${base}/challenge/check`, { method: "POST", body: JSON.stringify({ code }) }))}>{t("verifyContact")}</button></section>}
    {data?.access === "authorized" && <><p>{data.sandbox ? t("sandbox") : data.attribution === "matched_hiring_account" ? t("matched") : data.attribution === "contact_verified_relationship_declared" ? t("contactDeclared") : t("contactOnly")}</p>{data.identity_status && <p>{t("identity")}: {data.identity_status === "sandbox" ? t("sandbox") : data.identity_status === "verified" ? t("verified") : t("notVerified")}</p>}<section className="rounded-xl border p-4"><h2 className="font-semibold">{data.details?.work_type}</h2><p lang={data.details?.language}>{data.details?.description}</p><p>{data.details?.date_text || t("unknownDate")} · {data.details?.general_area || t("unknownArea")}</p><p>{t("completion")}: {data.details?.claimed_completed ? t("yes") : t("no")}</p></section>
      <button disabled={busy} onClick={() => void action(async () => { const r = await featureRequest<{ text: string }>(`${base}/description-translation`, { method:"POST", body:JSON.stringify({ target: language }) }, 95000); setTranslation(r.text); })}>{t("translatedSummary")}</button>{translation && <p>{t("translated")}: {translation}</p>}
      {uncertain && <p role="status">{t("uncertain")}</p>}
      <ClarificationThread base={base} />
      {data.response ? <><p role="status">{t("receipt")}: {data.response.decision}{data.response.withdrawn_at ? ` · ${t("withdrawn")}` : ""}</p>{!data.response.withdrawn_at && <button disabled={busy} onClick={() => void action(() => featureRequest(`${base}/response`, { method: "DELETE" }))}>{t("withdraw")}</button>}</> : <form className="flex flex-col gap-3" onSubmit={e => { e.preventDefault(); void action(respond); }}><fieldset disabled={busy || uncertain} className="flex flex-col gap-3"><label>{t("response")}<select value={decision} onChange={e => { setDecision(e.target.value); operation.current = null; }} className="block w-full rounded border p-2"><option value="confirmed">{t("confirmed")}</option><option value="incorrect">{t("incorrect")}</option><option value="unrecognized">{t("unrecognized")}</option></select></label><label><input type="checkbox" checked={declares} onChange={e => { setDeclares(e.target.checked); operation.current = null; }} /> {t("declares")}</label><label><input required type="checkbox" checked={consent} onChange={e => { setConsent(e.target.checked); operation.current = null; }} /> {t("consent")}</label></fieldset><button className="rounded bg-primary-500 p-3 text-white" disabled={busy || !consent || (decision === "confirmed" && !declares)}>{t("submit")}</button></form>}
    </>}
  </main>;
}

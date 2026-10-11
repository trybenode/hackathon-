"use client";
import Link from "next/link";
import { TranslatedAudio } from "./TranslatedAudio";
import { historyError, operationReceipt, uncertainFailure } from "@/lib/historyErrors";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiFailure, featureRequest, type Page } from "@/lib/portability";
import { historyDate } from "@/lib/history";
import type { Language } from "@/lib/history";
import { useLanguage } from "./LanguageProvider";
type Translation = { target: Language; status: string; text: string | null; error_code: string | null; model: string; model_revision?: string | null };
type Message = { id: string; operation_id: string; actor_role: string; text: string; language: Language; created_at: string; translations: Translation[] };

/** Asynchronous, job-scoped originals and translations. No live-chat simulation. */
export function ClarificationThread({ base }: { base: string }) {
  const { language, t } = useLanguage();
  const [data, setData] = useState<Page<Message> | null>(null);
  const [page, setPage] = useState(1);
  const [text, setText] = useState("");
  const [source, setSource] = useState<Language>(language);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const operation = useRef<string | null>(null);
  const pendingMessage = useRef<{ text: string; language: Language } | null>(null);
  const [threadUnavailable, setThreadUnavailable] = useState(false);
  const [speechLanguages, setSpeechLanguages] = useState<Language[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    const path = base.startsWith("/me/") ? "/me/history-speech-capabilities" : `${base}/speech-capabilities`;
    void featureRequest<{ languages: Language[] }>(path, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setSpeechLanguages(value.languages); }).catch(() => {});
    return () => controller.abort();
  }, [base]);
  const reportError = useCallback((e: unknown) => {
    const unavailable = e instanceof ApiFailure && e.code === "THREAD_UNAVAILABLE";
    setThreadUnavailable(unavailable);
    if (unavailable) setData(null);
    setError(historyError(e, t));
  }, [t]);
  const load = useCallback(async (signal?: AbortSignal) => { const result = await featureRequest<Page<Message>>(`${base}/messages?page=${page}`, { signal }); if (!signal?.aborted) { setData(result); setThreadUnavailable(false); setError(""); } }, [base, page]);
  useEffect(() => { const c = new AbortController(); void featureRequest<Page<Message>>(`${base}/messages?page=${page}`, { signal: c.signal }).then(value => { if (!c.signal.aborted) { setData(value); setThreadUnavailable(false); setError(""); } }).catch(e => { if (!c.signal.aborted) reportError(e); }); return () => c.abort(); }, [base, page, reportError]);
  async function send() {
    if (!data || threadUnavailable) return;
    setBusy(true); setError(""); operation.current ??= crypto.randomUUID();
    pendingMessage.current ??= { text, language: source };
    try { if (!(uncertain && await operationReceipt<Message>(`${base}/messages/operations/${operation.current}`))) await featureRequest<Message>(`${base}/messages`, { method:"POST", headers:{"Idempotency-Key":operation.current}, body:JSON.stringify(pendingMessage.current) }); setText(""); setUncertain(false); operation.current = null; pendingMessage.current = null; await load().catch(e => reportError(e)); }
    catch (e) { reportError(e); setUncertain(uncertainFailure(e)); if (!uncertainFailure(e)) { operation.current = null; pendingMessage.current = null; } }
    finally { setBusy(false); }
  }
  async function translate(id: string) {
    setBusy(true); setError("");
    try { await featureRequest<Translation>(`${base}/messages/${id}/translations`, { method:"POST", body:JSON.stringify({ target:language }) }, 95000); await load(); }
    catch (e) { reportError(e); }
    finally { setBusy(false); }
  }
  return <section className="history-journey flex flex-col gap-4 rounded-xl border p-4"><h2 className="font-semibold">{t("clarification")}</h2><p>{t("privacy")}</p><p className="text-xs">{t("futureChat")}</p>{error && <p role="alert">{error}</p>}{threadUnavailable && base.startsWith("/me/history-claims/") && <Link href="/worker/profile/record/history">{t("manage")}</Link>}{!data && !error && <p role="status">{t("loading")}</p>}{uncertain && <p role="status">{t("uncertain")}</p>}
    <form onSubmit={e => { e.preventDefault(); void send(); }} className="flex flex-col gap-3"><label>{t("language")}<select disabled={busy || uncertain || !data || threadUnavailable} value={source} onChange={e => setSource(e.target.value as Language)}>{["en","yo","ha","ig"].map(l => <option key={l} value={l}>{l}</option>)}</select></label><label>{t("message")}<textarea className="block w-full rounded border p-2" required maxLength={2000} value={text} disabled={busy || uncertain || !data || threadUnavailable} onChange={e => setText(e.target.value)} /></label><button disabled={busy || !data || threadUnavailable || !text.trim()}>{busy ? t("processing") : t("send")}</button></form>
    <button disabled={busy} onClick={() => void load().catch(e => reportError(e))}>{t("refresh")}</button>
    {data?.items.map(message => { const tr = message.translations.find(r => r.target === language); return <article key={message.id} className="rounded border p-3"><p className="text-xs">{message.actor_role} · {historyDate(message.created_at, language)} · {message.language}</p><p lang={message.language}>{t("original")}: {message.text}</p>{tr && <p lang={tr.target}>{tr.status === "ready" ? `${t("translated")} (${tr.target}, ${tr.model}, ${tr.model_revision || t("unknown")}): ${tr.text}` : `${t("translationFailed")}: ${tr.error_code}`}</p>}{tr?.status === "ready" && tr.text && <TranslatedAudio key={`${message.id}:${language}:${tr.text}`} base={`${base}/messages/${message.id}`} target={language} translation={tr.text} supported={speechLanguages.includes(language)} />}{message.language !== language && <button disabled={busy} onClick={() => void translate(message.id)}>{t("translate")}</button>}</article>; })}
    <nav className="flex justify-between"><button disabled={page <= 1 || busy} onClick={() => setPage(p => p-1)}>{t("previous")}</button><span>{page} / {data?.pages || 1}</span><button disabled={!data || page >= data.pages || busy} onClick={() => setPage(p => p+1)}>{t("next")}</button></nav>
  </section>;
}

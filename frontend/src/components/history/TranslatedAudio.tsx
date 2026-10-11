/** On-demand private speech: authorized fetches, native controls, no autoplay or persistent cache. */
"use client";
import { useEffect, useRef, useState } from "react";
import { apiBaseUrl } from "@/lib/api";
import { featureRequest } from "@/lib/portability";
import type { Language } from "@/lib/history";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";
import { useLanguage } from "./LanguageProvider";
import { historyError } from "@/lib/historyErrors";
type AudioStatus = { id: string; status: "queued" | "processing" | "ready" | "failed" | "expired"; error_code: string | null; model: string; version: string };
export function TranslatedAudio({ base, target, translation, supported }: { base: string; target: Language; translation: string; supported: boolean }) {
  const { w } = useWorkerCopy();
  const { t } = useLanguage();
  const [task, setTask] = useState<AudioStatus | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const objectUrl = useRef<string | null>(null);
  const active = useRef<AbortController | null>(null);
  useEffect(() => {
    return () => { active.current?.abort(); if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); };
  }, [base, target, translation]);
  async function listen() {
    setBusy(true); setError("");
    const controller = new AbortController(); active.current = controller;
    try {
      let current = task;
      if (!current || current.status === "failed" || current.status === "expired") current = await featureRequest<AudioStatus>(`${base}/audio`, { method: "POST", body: JSON.stringify({ target }), signal: controller.signal });
      else current = await featureRequest<AudioStatus>(`${base}/audio/${current.id}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setTask(current);
      if (current.status === "failed" || current.status === "expired") { setError(w("Audio unavailable")); return; }
      if (current.status !== "ready") return;
      const response = await fetch(`${apiBaseUrl}${base}/audio/${current.id}/content`, { credentials: "include", cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error(w("Audio unavailable"));
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = URL.createObjectURL(blob); setUrl(objectUrl.current);
    } catch (e) { if (!controller.signal.aborted) setError(historyError(e, t)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <div className="flex flex-col gap-2">
    {!supported ? <p className="text-xs">{w("Audio unavailable")}</p> : <button type="button" className="min-h-11 rounded border px-3" disabled={busy} onClick={() => void listen()}>{busy ? w("Preparing audio…") : task && ["queued","processing"].includes(task.status) ? t("refresh") : w("Listen")}</button>}
    {task && ["queued","processing"].includes(task.status) && <p role="status">{w("Preparing audio…")}</p>}
    {error && <p role="alert">{error}</p>}
    {url && <><audio controls preload="none" src={url} aria-label={`${w("Listen")} (${target})`} /><p className="text-xs">{t("translated")} · {target} · {task?.model} · {task?.version}</p></>}
  </div>;
}

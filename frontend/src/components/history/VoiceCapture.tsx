"use client";
import {
  historyError,
  operationReceipt,
  uncertainFailure,
} from "@/lib/historyErrors";
import { useEffect, useRef, useState } from "react";
import { featureRequest } from "@/lib/portability";
import type { Details } from "@/lib/history";
import { useLanguage } from "./LanguageProvider";
type Draft = {
  id: string;
  status: string;
  transcript: string | null;
  details: Details | null;
  error_code: string | null;
  claim_id: string | null;
  job_id: string | null;
};

/** Audio remains in memory; model output is an editable draft requiring worker approval. */
export function VoiceCapture({
  jobId,
  onDraft,
  onReset,
}: {
  jobId: string;
  onReset: () => void;
  onDraft: (details: Details, id: string, jobId: string | null) => void;
}) {
  const { language, t } = useLanguage();
  const [blob, setBlob] = useState<Blob | null>(null);
  const [url, setUrl] = useState("");
  const [recording, setRecording] = useState(false);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const uploadBody = useRef<FormData | null>(null);
  const [configured, setConfigured] = useState(false);
  const [maxAudioBytes, setMaxAudioBytes] = useState(5 * 1024 * 1024);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const operation = useRef<string | null>(null);
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    void featureRequest<{ voice_configured: boolean; audio_max_bytes?: number }>(
      "/me/history-capabilities",
    )
      .then((r) => {
        if (live.current) {
          setConfigured(r.voice_configured);
          if (r.audio_max_bytes && r.audio_max_bytes > 0) setMaxAudioBytes(r.audio_max_bytes);
        }
      })
      .catch(() => undefined);
    return () => {
      live.current = false;
      if (timeout.current) clearTimeout(timeout.current);
      if (recorder.current) {
        recorder.current.onstop = null;
        if (recorder.current.state !== "inactive") recorder.current.stop();
      }
      stream.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  function chooseBlob(value: Blob) {
    onReset();
    setBlob(value);
    setUrl(URL.createObjectURL(value));
    setDraft(null);
    operation.current = null;
    uploadBody.current = null;
  }
  useEffect(() => {
    if (!draft || !["queued", "processing"].includes(draft.status)) return;
    const controller = new AbortController();
    const timer = setInterval(() => {
      void featureRequest<Draft>(`/me/history-drafts/${draft.id}`, {
        signal: controller.signal,
      })
        .then((r) => {
          if (!controller.signal.aborted) {
            setDraft(r);
            setUncertain(false);
            if (r.status === "ready" && r.details)
              onDraft(r.details, r.id, r.job_id);
          }
        })
        .catch((e) => {
          if (!controller.signal.aborted) setError(historyError(e, t));
        });
    }, 4000);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [draft, onDraft, t]);
  function stop() {
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (timeout.current) clearTimeout(timeout.current);
  }
  async function record() {
    setError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)
        throw new Error(t("recordingUnavailable"));
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!live.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const mime = [
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/ogg;codecs=opus",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      const instance = new MediaRecorder(media, {
        ...(mime ? { mimeType: mime } : {}),
        audioBitsPerSecond: 24000,
      });
      recorder.current = instance;
      const chunks: BlobPart[] = [];
      instance.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      instance.onstop = () => {
        media.getTracks().forEach((track) => track.stop());
        if (live.current) {
          setRecording(false);
          chooseBlob(new Blob(chunks, { type: instance.mimeType }));
        }
      };
      instance.start();
      setRecording(true);
      timeout.current = setTimeout(stop, 60000);
    } catch (e) {
      stream.current?.getTracks().forEach((track) => track.stop());
      setError(historyError(e, t));
    }
  }
  async function upload() {
    if (!blob) return;
    setBusy(true);
    setError("");
    operation.current ??= crypto.randomUUID();
    const body = uploadBody.current || new FormData();
    if (!uploadBody.current) {
      body.set("audio", blob, "recording");
      body.set("language", language);
      body.set("consent", String(consent));
      if (jobId) body.set("job_id", jobId);
      uploadBody.current = body;
    }
    try {
      const r =
        (uncertain
          ? await operationReceipt<Draft>(
              `/me/history-drafts/operations/${operation.current}`,
            )
          : null) ??
        (await featureRequest<Draft>("/me/history-drafts", {
          method: "POST",
          headers: { "Idempotency-Key": operation.current },
          body,
        }));
      setDraft(r);
      setUncertain(false);
      if (r.status === "ready" && r.details) onDraft(r.details, r.id, r.job_id);
    } catch (e) {
      setError(historyError(e, t));
      const unknown = uncertainFailure(e);
      setUncertain(unknown);
      if (!unknown) uploadBody.current = null;
    } finally {
      setBusy(false);
    }
  }
  const processing = !!draft && ["queued", "processing"].includes(draft.status);
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-stroke p-4">
      <p>{t("voiceHint")}</p>
      <p className="text-xs">{t("reviewDraft")}</p>
      {!configured && (
        <p role="status">{t("serviceUnavailable")} — ASR / ffmpeg</p>
      )}
      <label>
        <input
          type="checkbox"
          checked={consent}
          disabled={busy || uncertain || processing}
          onChange={(e) => setConsent(e.target.checked)}
        />{" "}
        {t("audioConsent")}
      </label>
      <div className="flex flex-wrap gap-4">
        <button
          type="button"
          disabled={!consent || busy || uncertain || processing}
          onClick={() => void (recording ? stop() : record())}
        >
          {recording ? t("stop") : t("recordVoice")}
        </button>
        <label>
          {t("upload")}
          <input
            type="file"
            accept="audio/*"
            disabled={!consent || busy || uncertain || recording || processing}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                if (file.size > maxAudioBytes) {
                  setError(`Maximum ${Math.floor(maxAudioBytes / (1024 * 1024))} MB`);
                  return;
                }
                chooseBlob(file);
              }
            }}
          />
        </label>
      </div>
      {url && <audio controls src={url} preload="metadata" />}
      <button
        type="button"
        disabled={
          !blob || !consent || !configured || busy || recording || processing
        }
        onClick={() => void upload()}
      >
        {busy || processing ? t("processing") : t("processAudio")}
      </button>
      {uncertain && <p role="status">{t("uncertain")}</p>}
      {draft?.status === "failed" && (
        <>
          <p role="alert">
            {draft.error_code} · {t("serviceUnavailable")}
          </p>
          <button
            type="button"
            onClick={() => {
              void featureRequest<Draft>(
                `/me/history-drafts/${draft.id}/retry`,
                { method: "POST" },
              )
                .then(setDraft)
                .catch((e) => setError(historyError(e, t)));
            }}
          >
            {t("retry")}
          </button>
        </>
      )}
      {draft?.transcript && (
        <div>
          <p>{t("original")}</p>
          <p>{draft.transcript}</p>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

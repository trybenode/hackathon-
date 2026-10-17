"use client";
/** Worker-owned CSV preview and separate private attachment upload; uncertain writes reconcile before retry. */
import { useRef, useState } from "react";
import { apiBaseUrl } from "@/lib/api";
import { ApiFailure, errorMessage } from "@/lib/portability";
import {
  attachDocument,
  getImport,
  importReceipt,
  prepareImport,
  submitImport,
  type ImportBatch,
} from "@/lib/admission";
import { stateCopy, useReviewCopy } from "./ReviewLanguage";
export function UnsignedImportPanel({
  onSubmitted,
  replaces,
}: {
  onSubmitted: () => Promise<void>;
  replaces?: string;
}) {
  const { t } = useReviewCopy();
  const [file, setFile] = useState<File | null>(null);
  const [document, setDocument] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState("");
  const operation = useRef<string | null>(null);
  function fail(cause: unknown) {
    setError(errorMessage(cause));
    setUncertain(
      !(cause instanceof ApiFailure) ||
        cause.status === 0 ||
        cause.status >= 500,
    );
  }
  async function preview() {
    if (!file) return;
    setBusy(true);
    setError("");
    operation.current ??= crypto.randomUUID();
    try {
      setBatch(await prepareImport(file, source, operation.current, replaces));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function send() {
    if (!batch || !document) return;
    setBusy(true);
    setError("");
    try {
      let current = batch;
      if (!current.document_present) {
        current = await attachDocument(current.id, document);
        setBatch(current);
      }
      current = await submitImport(current);
      setBatch(current);
      await onSubmitted();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function reconcile() {
    setBusy(true);
    setError("");
    try {
      const current = batch
        ? await getImport(batch.id)
        : operation.current
          ? await importReceipt(operation.current)
          : null;
      if (current) setBatch(current);
      setUncertain(false);
      await onSubmitted();
    } catch (e) {
      if (e instanceof ApiFailure && e.status === 404) {
        setUncertain(false);
        setError(t("receiptMissing"));
      } else fail(e);
    } finally {
      setBusy(false);
    }
  }
  const submitted = !!batch && batch.state !== "preparing";
  return (
    <section className="flex flex-col gap-4 rounded-xl border border-stroke p-4">
      <h2 className="font-semibold">{t("unsigned")}</h2>
      <p className="text-sm">{t("note")}</p>
      <p className="text-sm">{t("binding")}</p>
      <p className="text-sm">{t("retention")}</p>
      <a
        className="underline"
        href={`${apiBaseUrl}/me/history-imports/template`}
      >
        {t("template")}
      </a>
      {error && (
        <p role="alert" className="text-error">
          {error}
        </p>
      )}
      {uncertain ? (
        <button
          type="button"
          className="min-h-11 rounded border px-4"
          disabled={busy}
          onClick={() => void reconcile()}
        >
          {busy ? t("busy") : t("reconcile")}
        </button>
      ) : null}
      <fieldset
        disabled={busy || uncertain || submitted}
        className="flex flex-col gap-4"
      >
        <label>
          {t("source")}
          <input
            className="block w-full rounded border p-2"
            value={source}
            maxLength={120}
            disabled={!!batch}
            onChange={(e) => setSource(e.target.value)}
          />
        </label>
        <label>
          {t("csv")}
          <input
            className="block w-full"
            type="file"
            accept=".csv,text/csv"
            disabled={!!batch}
            onChange={(e) => {
              const next = e.target.files?.[0] || null;
              if (next && next.size > 2 * 1024 * 1024) {
                setError(t("tooLarge"));
                return;
              }
              setFile(next);
              operation.current = null;
            }}
          />
        </label>
        <label>
          {t("document")}
          <input
            className="block w-full"
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            disabled={batch?.document_present}
            onChange={(e) => {
              const next = e.target.files?.[0] || null;
              if (next && next.size > 3 * 1024 * 1024) {
                setError(t("tooLarge"));
                return;
              }
              setDocument(next);
            }}
          />
        </label>
        <label className="flex gap-2">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
          />
          {t("consent")}
        </label>
        {!batch ? (
          <button
            type="button"
            className="min-h-11 rounded border px-4"
            disabled={!file || !source.trim() || !agreed}
            onClick={() => void preview()}
          >
            {t("preview")}
          </button>
        ) : (
          <button
            type="button"
            className="min-h-11 rounded border px-4"
            disabled={!document || !agreed}
            onClick={() => void send()}
          >
            {submitted ? t("submitted") : t("submit")}
          </button>
        )}
      </fieldset>
      {batch && !uncertain && (
        <button
          type="button"
          className="min-h-11 rounded border px-4"
          disabled={busy}
          onClick={() => {
            setBatch(null);
            operation.current = null;
            setError("");
          }}
        >
          {t("newImport")}
        </button>
      )}
      {batch && (
        <div role="status">
          <p>
            {stateCopy(
              batch.state === "approved" ? "ownership_approved" : batch.state,
              t,
            )}{" "}
            · {batch.row_count}
          </p>
          <ul className="max-h-64 overflow-auto text-sm">
            {batch.rows.slice(0, 20).map((row) => (
              <li key={row.job_id}>
                {row.job_id} · {row.date} · {stateCopy(row.status, t)}
              </li>
            ))}
          </ul>
          {batch.rows.length > 20 && <p>20 / {batch.row_count}</p>}
        </div>
      )}
    </section>
  );
}

"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";
import {
  historyError,
  operationReceipt,
  uncertainFailure,
} from "@/lib/historyErrors";
import Link from "next/link";
import { VoiceCapture } from "@/components/history/VoiceCapture";
import {
  useLanguage,
} from "@/components/history/LanguageProvider";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiFailure, featureRequest, type Page } from "@/lib/portability";
import { historyDate } from "@/lib/history";
import type { Claim, Confirmation, Details } from "@/lib/history";

const empty: Details = {
  work_type: "",
  description: "",
  date_text: null,
  general_area: null,
  claimed_completed: true,
  language: "en",
};
type Job = { id: string; title: string };

/** Text-first history; stable operations reconcile uncertain writes without duplicates. */
export function HistoryManager() {
  const { w } = useWorkerCopy();

  const { language, t } = useLanguage();
  const [details, setDetails] = useState<Details>(empty);
  const [voiceReset, setVoiceReset] = useState(0);
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const onVoiceReset = useCallback(() => setVoiceId(null), []);
  const [jobId, setJobId] = useState("");
  const onVoiceDraft = useCallback(
    (value: Details, id: string, sourceJob: string | null) => {
      setDetails(value);
      setVoiceId(id);
      setJobId(sourceJob || "");
    },
    [],
  );
  const [jobPage, setJobPage] = useState(1);
  const [jobPages, setJobPages] = useState(0);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [claims, setClaims] = useState<Page<Claim> | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [edit, setEdit] = useState<Claim | null>(null);
  const [phones, setPhones] = useState<Record<string, string>>({});
  const [requests, setRequests] = useState<Record<string, Page<Confirmation>>>(
    {},
  );
  const [share, setShare] = useState<{ url: string; expiry: string } | null>(
    null,
  );
  const [pendingInvite, setPendingInvite] = useState<string | null>(null);
  const [previewPhone, setPreviewPhone] = useState("");
  const [preview, setPreview] = useState<Claim | null>(null);
  const pendingSave = useRef<{
    job_id: string | null;
    details: Details;
  } | null>(null);
  const requestPayloads = useRef<
    Record<string, { revision: number; recipient_phone: string | null }>
  >({});
  const operation = useRef<string | null>(null);
  const requestOperations = useRef<Record<string, string>>({});
  const load = useCallback(
    async (signal?: AbortSignal) => {
      const data = await featureRequest<Page<Claim>>(
        `/me/history-claims?page=${page}`,
        { signal },
      );
      if (!signal?.aborted) setClaims(data);
    },
    [page],
  );
  useEffect(() => {
    const controller = new AbortController();
    void featureRequest<Page<Claim>>(`/me/history-claims?page=${page}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setClaims(value);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(historyError(e, t));
      });
    return () => controller.abort();
  }, [page, t]);
  useEffect(() => {
    const controller = new AbortController();
    void featureRequest<Page<Job>>(`/me/history-jobs?page=${jobPage}&size=20`, {
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          if (!Array.isArray(data.items) || !Number.isInteger(data.pages))
            throw new Error("Invalid job choices response. Reload and retry.");
          setJobs(data.items);
          setJobPages(data.pages);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(historyError(e, t));
      });
    return () => controller.abort();
  }, [jobPage, t]);
  async function save() {
    setBusy(true);
    setError("");
    operation.current ??= crypto.randomUUID();
    pendingSave.current ??= {
      job_id: jobId || null,
      details: { ...details, language: voiceId ? details.language : language },
    };
    const payload = pendingSave.current;
    try {
      let editedAlready = false;
      if (uncertain && edit) {
        const current = await featureRequest<Claim>(
          `/me/history-claims/${edit.id}`,
        );
        if (current.revision !== edit.revision) {
          editedAlready =
            current.revision === edit.revision + 1 &&
            Object.entries(payload.details).every(
              ([key, value]) => current.details[key as keyof Details] === value,
            );
          if (!editedAlready)
            throw new Error(
              "The claim changed. Reload the current record before correcting it.",
            );
        }
      }
      if (voiceId && !edit)
        await featureRequest<Claim>(`/me/history-drafts/${voiceId}/save`, {
          method: "POST",
          body: JSON.stringify({ details: payload.details, approved: true }),
        });
      else if (edit && !editedAlready)
        await featureRequest<Claim>(`/me/history-claims/${edit.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            revision: edit.revision,
            details: payload.details,
          }),
        });
      else if (
        !edit &&
        !(
          uncertain &&
          (await operationReceipt<Claim>(
            `/me/history-claims/operations/${operation.current}`,
          ))
        )
      )
        await featureRequest<Claim>("/me/history-claims", {
          method: "POST",
          headers: { "Idempotency-Key": operation.current },
          body: JSON.stringify(payload),
        });
      operation.current = null;
      pendingSave.current = null;
      setUncertain(false);
      setEdit(null);
      setVoiceId(null);
      setVoiceReset((v) => v + 1);
      setDetails(empty);
      setJobId("");
      await load().catch((e) => setError(historyError(e, t)));
    } catch (e) {
      setError(historyError(e, t));
      const unknown = uncertainFailure(e);
      setUncertain(unknown);
      if (!unknown) {
        pendingSave.current = null;
        operation.current = null;
      }
    } finally {
      setBusy(false);
    }
  }
  async function listRequests(claim: Claim, requestedPage = 1) {
    const data = await featureRequest<Page<Confirmation>>(
      `/me/history-claims/${claim.id}/confirmation-requests?page=${requestedPage}`,
    );
    setRequests((current) => ({ ...current, [claim.id]: data }));
  }
  async function invite(claim: Claim) {
    setBusy(true);
    setError("");
    setShare(null);
    setPendingInvite(claim.id);
    const reconcile = !!requestOperations.current[claim.id];
    requestOperations.current[claim.id] ??= crypto.randomUUID();
    requestPayloads.current[claim.id] ??= {
      revision: claim.revision,
      recipient_phone: claim.job_id ? null : phones[claim.id] || null,
    };
    const payload = requestPayloads.current[claim.id];
    try {
      let result =
        (reconcile
          ? await operationReceipt<Confirmation>(
              `/me/history-claims/${claim.id}/confirmation-requests/operations/${requestOperations.current[claim.id]}`,
            )
          : null) ??
        (await featureRequest<Confirmation>(
          `/me/history-claims/${claim.id}/confirmation-requests`,
          {
            method: "POST",
            headers: { "Idempotency-Key": requestOperations.current[claim.id] },
            body: JSON.stringify(payload),
          },
        ));
      if (!result.token) {
        await featureRequest(`/me/confirmation-requests/${result.id}`, {
          method: "DELETE",
        });
        requestOperations.current[claim.id] = crypto.randomUUID();
        result = await featureRequest<Confirmation>(
          `/me/history-claims/${claim.id}/confirmation-requests`,
          {
            method: "POST",
            headers: { "Idempotency-Key": requestOperations.current[claim.id] },
            body: JSON.stringify(payload),
          },
        );
      }
      if (!result.token)
        throw new Error(
          "The returned link could not be recovered. Revoke and replace the request.",
        );
      setShare({
        url: `${location.origin}/confirm-work/${result.token}`,
        expiry: result.expires_at,
      });
      delete requestOperations.current[claim.id];
      delete requestPayloads.current[claim.id];
      setPreview(null);
      setPendingInvite(null);
      await listRequests(claim);
    } catch (e) {
      setError(historyError(e, t));
      if (e instanceof ApiFailure && !uncertainFailure(e)) {
        setPendingInvite(null);
        delete requestOperations.current[claim.id];
        delete requestPayloads.current[claim.id];
      }
    } finally {
      setBusy(false);
    }
  }
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(historyError(e, t));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="history-journey mx-auto flex w-full max-w-xl flex-col gap-5 p-5">
      <Link href="/worker/profile/record">← {t("record")}</Link>
      {/* <LanguageSelector /> */}
      <h1 className="text-h3 font-semibold">{t("historyTitle")}</h1>
      <p>{t("scoreUnchanged")}</p>
      {error && <p role="alert">{w(error)}</p>}{" "}
      {uncertain && <p role="status">{t("uncertain")}</p>}
      {!edit && !uncertain && (
        <VoiceCapture
          key={voiceReset}
          jobId={jobId}
          onDraft={onVoiceDraft}
          onReset={onVoiceReset}
        />
      )}
      <form
        className="flex flex-col gap-3 rounded-xl border border-stroke p-4"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <fieldset disabled={busy || uncertain} className="flex flex-col gap-3">
          <label>
            {t("jobSource")}
            <select
              className="block w-full rounded border p-2"
              disabled={!!edit || !!voiceId}
              value={jobId}
              onChange={(e) => {
                setJobId(e.target.value);
                if (e.target.value)
                  setDetails((d) => ({
                    ...d,
                    work_type:
                      jobs.find((j) => j.id === e.target.value)?.title || "Job",
                  }));
              }}
            >
              <option value="">{t("informal")}</option>
              {jobId && !jobs.some((j) => j.id === jobId) && (
                <option value={jobId}>{details.work_type}</option>
              )}
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}
                </option>
              ))}
            </select>
          </label>
          {jobPages > 1 && !edit && (
            <nav className="flex justify-between">
              <button
                type="button"
                disabled={jobPage === 1}
                onClick={() => setJobPage((p) => p - 1)}
              >
                {t("previous")}
              </button>
              <span>
                {t("jobSource")} {jobPage} / {jobPages}
              </span>
              <button
                type="button"
                disabled={jobPage >= jobPages}
                onClick={() => setJobPage((p) => p + 1)}
              >
                {t("next")}
              </button>
            </nav>
          )}
          <label>
            {t("workType")}
            <input
              required
              maxLength={100}
              value={details.work_type}
              disabled={!!jobId || !!edit?.job_id}
              onChange={(e) =>
                setDetails((d) => ({ ...d, work_type: e.target.value }))
              }
              className="block w-full rounded border p-2"
            />
          </label>
          <label>
            {t("description")}
            <textarea
              required
              maxLength={2000}
              value={details.description}
              onChange={(e) =>
                setDetails((d) => ({ ...d, description: e.target.value }))
              }
              className="block w-full rounded border p-2"
            />
          </label>
          {!jobId && !edit?.job_id && (
            <>
              <label>
                {t("approximateDate")}
                <input
                  maxLength={100}
                  value={details.date_text || ""}
                  onChange={(e) =>
                    setDetails((d) => ({
                      ...d,
                      date_text: e.target.value || null,
                    }))
                  }
                  className="block w-full rounded border p-2"
                />
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={details.claimed_completed}
                  onChange={(e) =>
                    setDetails((d) => ({
                      ...d,
                      claimed_completed: e.target.checked,
                    }))
                  }
                />{" "}
                {t("completed")}
              </label>
            </>
          )}
          <label>
            {t("area")}
            <input
              maxLength={160}
              value={details.general_area || ""}
              onChange={(e) =>
                setDetails((d) => ({
                  ...d,
                  general_area: e.target.value || null,
                }))
              }
              className="block w-full rounded border p-2"
            />
          </label>
        </fieldset>
        <button
          className="rounded bg-primary-500 p-3 text-white"
          disabled={busy}
        >
          {busy ? t("saving") : edit ? t("correction") : t("save")}
        </button>
        {edit && !uncertain && (
          <button
            type="button"
            onClick={() => {
              setEdit(null);
              setDetails(empty);
            }}
          >
            {t("cancel")}
          </button>
        )}
      </form>
      {preview && (
        <section
          role="dialog"
          aria-label={t("invite")}
          className="flex flex-col gap-3 rounded-xl border p-4"
        >
          <h2>{t("invite")}</h2>
          <p>
            {preview.details.work_type} · {preview.details.description}
          </p>
          <p>
            {preview.job_id
              ? t("accountRequired")
              : `${t("phone")}: ${previewPhone || "—"}`}
          </p>
          <p>{t("privacy")}</p>
          <button disabled={busy} onClick={() => void invite(preview)}>
            {t("generate")}
          </button>
          <button
            disabled={busy || pendingInvite === preview.id}
            onClick={() => setPreview(null)}
          >
            {t("cancel")}
          </button>
        </section>
      )}
      {share && (
        <section className="break-all rounded border p-4">
          <p>
            {t("expires")}: {historyDate(share.expiry, language)}
          </p>
          <a href={share.url}>{share.url}</a>
          <div className="flex gap-4">
            <button
              onClick={() =>
                void navigator.clipboard
                  .writeText(share.url)
                  .catch(() => setError(t("copyFailed")))
              }
            >
              {t("copy")}
            </button>
            <a
              href={`https://wa.me/?text=${encodeURIComponent(share.url)}`}
              target="_blank"
              rel="noreferrer"
            >
              {t("whatsapp")}
            </a>
          </div>
        </section>
      )}
      {
        <button disabled={busy} onClick={() => void action(() => load())}>
          {t("retry")}
        </button>
      }
      {claims?.total === 0 && <p>{t("noHistory")}</p>}
      {claims?.items.map((claim) => (
        <article
          key={claim.id}
          className="flex flex-col gap-3 rounded-xl border border-stroke p-4"
        >
          <h2 className="font-semibold">{claim.details.work_type}</h2>
          <p>{claim.details.description}</p>
          <p>
            {claim.details.date_text || t("unknownDate")} ·{" "}
            {claim.details.general_area || t("unknownArea")}
          </p>
          <p>
            {claim.response
              ? `${claim.response.decision} · ${claim.response.sandbox ? t("sandbox") : claim.response.attribution === "matched_hiring_account" ? t("matched") : claim.response.attribution === "contact_verified_relationship_declared" ? t("contactDeclared") : t("contactOnly")}${claim.response.withdrawn_at ? ` · ${t("withdrawn")}` : ""}`
              : `${t("selfDeclared")} · ${t("noResponse")}`}
          </p>
          {!claim.job_id && (
            <label>
              {t("phone")}
              <input
                placeholder={w("+2348012345678")}
                disabled={busy || pendingInvite === claim.id}
                value={phones[claim.id] || ""}
                onChange={(e) =>
                  setPhones((p) => ({ ...p, [claim.id]: e.target.value }))
                }
                className="block w-full rounded border p-2"
              />
            </label>
          )}
          <div className="flex flex-wrap gap-4">
            <button
              disabled={busy}
              onClick={() => {
                setPreview(claim);
                setPreviewPhone(phones[claim.id] || "");
              }}
            >
              {t("invite")}
            </button>
            <button
              disabled={busy || uncertain}
              onClick={() => {
                setEdit(claim);
                setDetails(claim.details);
                setJobId(claim.job_id || "");
              }}
            >
              {t("edit")}
            </button>
            <button
              disabled={busy}
              onClick={() =>
                void action(() =>
                  featureRequest(`/me/history-claims/${claim.id}`, {
                    method: "DELETE",
                  }),
                )
              }
            >
              {t("archive")}
            </button>
            <Link href={`/worker/profile/record/history/${claim.id}`}>
              {t("clarify")}
            </Link>
            <button
              disabled={busy}
              onClick={() => void action(() => listRequests(claim))}
            >
              {t("manage")}
            </button>
          </div>
          {requests[claim.id]?.items.map((r) => (
            <div key={r.id}>
              <span>
                {r.revoked_at
                  ? t("revoked")
                  : new Date(r.expires_at) <= new Date()
                    ? t("expired")
                    : t("active")}{" "}
                · {historyDate(r.expires_at, language)}
              </span>
              {!r.revoked_at && (
                <button
                  disabled={busy}
                  className="ml-3"
                  onClick={() =>
                    void action(async () => {
                      await featureRequest(
                        `/me/confirmation-requests/${r.id}`,
                        { method: "DELETE" },
                      );
                      await listRequests(claim);
                    })
                  }
                >
                  {t("revoke")}
                </button>
              )}
            </div>
          ))}
          {requests[claim.id] && requests[claim.id].pages > 1 && (
            <nav className="flex justify-between">
              <button
                disabled={busy || requests[claim.id].page === 1}
                onClick={() =>
                  void action(() =>
                    listRequests(claim, requests[claim.id].page - 1),
                  )
                }
              >
                {t("previous")}
              </button>
              <span>
                {requests[claim.id].page} / {requests[claim.id].pages}
              </span>
              <button
                disabled={
                  busy || requests[claim.id].page >= requests[claim.id].pages
                }
                onClick={() =>
                  void action(() =>
                    listRequests(claim, requests[claim.id].page + 1),
                  )
                }
              >
                {t("next")}
              </button>
            </nav>
          )}
        </article>
      ))}
      <nav className="flex justify-between">
        <button
          disabled={page === 1 || busy}
          onClick={() => setPage((p) => p - 1)}
        >
          {t("previous")}
        </button>
        <span>
          {page} / {claims?.pages || 1}
        </span>
        <button
          disabled={!claims || page >= claims.pages || busy}
          onClick={() => setPage((p) => p + 1)}
        >
          {t("next")}
        </button>
      </nav>
    </main>
  );
}

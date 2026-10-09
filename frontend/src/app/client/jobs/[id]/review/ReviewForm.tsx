"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import {
  ApiFailure,
  dateLabel,
  errorMessage,
  featureRequest,
  getReviewEligibility,
  type ReviewEligibility,
  type ReviewReceipt,
} from "@/lib/portability";

export function ReviewForm({ jobId }: { jobId: string }) {
  const [eligibility, setEligibility] = useState<ReviewEligibility | null>(
    null,
  );
  const [rating, setRating] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<ReviewReceipt | null>(null);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [revision, setRevision] = useState(0);
  const [wait, setWait] = useState(0);
  const attempt = useRef<{ body: string; key: string } | null>(null);
  useEffect(() => {
    let active = true;
    getReviewEligibility(jobId)
      .then((value) => {
        if (active) {
          setEligibility(value);
          setReceipt(value.existing_review);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    return () => {
      active = false;
    };
  }, [jobId, revision]);
  useEffect(() => {
    if (!wait) return;
    const timer = setTimeout(() => setWait((v) => Math.max(0, v - 1)), 1000);
    return () => clearTimeout(timer);
  }, [wait]);
  async function reconcile() {
    setBusy(true);
    setError("");
    try {
      const current = await getReviewEligibility(jobId);
      setEligibility(current);
      setReceipt(current.existing_review);
      setUncertain(false);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function submit() {
    setBusy(true);
    setError("");
    try {
      // Reconcile a prior lost response and refresh server eligibility before writing.
      const current = await getReviewEligibility(jobId);
      setEligibility(current);
      if (current.existing_review) {
        setReceipt(current.existing_review);
        setUncertain(false);
        return;
      }
      if (!current.eligible) return;
      const body = JSON.stringify({
        rating: Number(rating),
        comment: comment.trim() || null,
      });
      if (!attempt.current || attempt.current.body !== body)
        attempt.current = { body, key: crypto.randomUUID() };
      const result = await featureRequest<ReviewReceipt>(
        `/jobs/${encodeURIComponent(jobId)}/review`,
        {
          method: "POST",
          headers: { "Idempotency-Key": attempt.current.key },
          body,
        },
      );
      setReceipt(result);
      setUncertain(false);
    } catch (e) {
      setError(errorMessage(e));
      if (e instanceof ApiFailure) {
        setUncertain(e.status === 0);
        if (e.retryAfter) setWait(e.retryAfter);
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="mx-auto flex w-full max-w-lg flex-col gap-5 p-6">
      <header>
        <p className="text-body-sm text-info">
          Confirmed work · accountable feedback
        </p>
        <h1 className="mt-1 text-h3 font-semibold text-navy-500">
          Review your job
        </h1>
      </header>
      {error && (
        <p role="alert" className="rounded-lg bg-error-light p-4 text-body-sm">
          {error}
        </p>
      )}
      {!eligibility && !error && (
        <p role="status">Checking review eligibility…</p>
      )}
      {eligibility && (
        <h2 className="text-body-lg font-medium">{eligibility.job_title}</h2>
      )}
      {receipt ? (
        <section className="rounded-xl bg-success-light p-5" role="status">
          <h2 className="text-body-lg font-semibold">Review recorded</h2>
          <p className="mt-2">
            Rating {receipt.rating}/5 · {dateLabel(receipt.submitted_at)}
          </p>
          <p className="mt-2 text-body-sm">
            One review is allowed for this job. Your comment stays private.
          </p>
        </section>
      ) : eligibility && !eligibility.eligible ? (
        <section className="rounded-xl border border-stroke p-5">
          <h2 className="font-semibold">Review unavailable</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-body-sm">
            {eligibility.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>
      ) : (
        eligibility && (
          <section className="flex flex-col gap-5 rounded-xl border border-stroke p-5">
            {eligibility.sandbox_identity && (
              <p className="rounded-lg bg-warning-light p-3 text-body-sm">
                Your identity check uses sandbox evidence in this demo.
              </p>
            )}
            <p className="text-body-sm text-grey-600">
              Only the verified hiring customer can review a completed protected
              job. One review is allowed; your comment stays private.
            </p>
            <label className="text-body-sm">
              Rating
              <select
                value={rating}
                disabled={busy || uncertain}
                onChange={(e) => setRating(e.target.value)}
                className="mt-2 min-h-12 w-full rounded-lg border border-stroke p-3"
              >
                <option value="">Choose a rating</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n} / 5
                  </option>
                ))}
              </select>
            </label>
            <label className="text-body-sm">
              Comment (optional)
              <textarea
                value={comment}
                disabled={busy || uncertain}
                onChange={(e) => setComment(e.target.value)}
                maxLength={2000}
                rows={5}
                className="mt-2 w-full rounded-lg border border-stroke p-3"
              />
              <span className="block text-right text-xs text-grey-600">
                {comment.length}/2000
              </span>
            </label>
            {wait > 0 && (
              <p role="status" className="text-body-sm">
                Retry available in {wait} seconds. Your draft is preserved.
              </p>
            )}
            <Button
              disabled={busy || !rating || uncertain || wait > 0}
              onClick={submit}
            >
              {busy ? "Checking / submitting…" : "Submit review"}
            </Button>
          </section>
        )
      )}
      {!receipt && (
        <Button
          variant="outline"
          disabled={busy}
          onClick={uncertain ? reconcile : () => setRevision((v) => v + 1)}
        >
          {uncertain
            ? "Check whether submission completed"
            : "Refresh eligibility"}
        </Button>
      )}
    </main>
  );
}

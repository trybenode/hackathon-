"use client";
import { useRef, useState } from "react";
import {
  ApiFailure,
  errorMessage,
  featureRequest,
  type Grant,
} from "@/lib/portability";

/** Reuse one operation until its receipt is reconciled or explicitly revoked. */
export function useGrantCreation(path: string) {
  const inFlight = useRef(false);
  const attempt = useRef<{ key: string; body: string } | null>(null);
  const [issued, setIssued] = useState<Grant | null>(null);
  const [lost, setLost] = useState<Grant | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function create(payload?: unknown) {
    if (inFlight.current || uncertain || lost) return;
    const body = payload === undefined ? "" : JSON.stringify(payload);
    if (attempt.current && attempt.current.body !== body) {
      setError(
        "Finish or reconcile the previous approval before changing its details.",
      );
      return;
    }
    attempt.current ??= { key: crypto.randomUUID(), body };
    inFlight.current = true;
    setBusy(true);
    setError("");
    setIssued(null);
    try {
      const grant = await featureRequest<Grant>(path, {
        method: "POST",
        headers: { "Idempotency-Key": attempt.current.key },
        ...(body ? { body } : {}),
      });
      if (grant.token) {
        setIssued(grant);
        attempt.current = null;
      } else setLost(grant);
      return grant;
    } catch (e) {
      setError(errorMessage(e));
      if (e instanceof ApiFailure && (e.status === 0 || e.status >= 500))
        setUncertain(true);
      else attempt.current = null;
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  async function check() {
    if (inFlight.current || !attempt.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const grant = await featureRequest<Grant>(
        `${path}/operations/${attempt.current.key}`,
      );
      setLost(grant);
      setUncertain(false);
    } catch (e) {
      if (e instanceof ApiFailure && e.status === 404) {
        setUncertain(false);
        setError(
          "No completed operation was found. Retry with the same details; the operation identifier is preserved.",
        );
      } else setError(errorMessage(e));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  async function revokeLost() {
    if (inFlight.current || !lost) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      await featureRequest(`${path}/${lost.id}`, { method: "DELETE" });
      setLost(null);
      attempt.current = null;
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return {
    issued,
    clearIssued: () => setIssued(null),
    lost,
    uncertain,
    busy,
    error,
    create,
    check,
    revokeLost,
  };
}

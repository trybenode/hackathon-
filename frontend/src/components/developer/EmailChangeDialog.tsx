"use client";

import { useState, type FormEvent } from "react";
import { OtpInput } from "@/components/guarantor/OtpInput";
import { Button, Input, Modal } from "@/components/ui";
import { confirmEmailChange, requestEmailChange } from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

/** "Change email": a code goes to the new address, and entering it moves the account. */
export function EmailChangeDialog({
  current,
  onClose,
  onChanged,
}: {
  current: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Shown only in development, where the API returns the code. */
  const [debugCode, setDebugCode] = useState<string | null>(null);

  function fail(cause: unknown, fallback: string) {
    setError(cause instanceof ApiError ? cause.message : fallback);
  }

  async function send(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await requestEmailChange(email.trim());
      setDebugCode(result.debug_code);
      setSent(true);
    } catch (cause) {
      fail(cause, "Could not send a code. Check the address.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(value = code) {
    if (value.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      await confirmEmailChange(email.trim(), value);
      onChanged();
    } catch (cause) {
      setCode("");
      fail(cause, "Could not confirm that code.");
      setBusy(false);
    }
  }

  return (
    <Modal open title="Change email" hideTitle onClose={onClose}>
      <div className="flex w-full flex-col gap-5 text-left">
        <div className="flex flex-col gap-1">
          <h2 className="text-h3 text-grey-900">Change email</h2>
          <p className="text-body-sm text-grey-600">
            {sent
              ? `Enter the 6-digit code we sent to ${email.trim()}.`
              : `Currently ${current}. We'll send a code to the new address to confirm it's yours.`}
          </p>
        </div>

        {!sent ? (
          <form onSubmit={send} className="flex flex-col gap-5">
            <Input
              type="email"
              label="New email address"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
            {error && (
              <p role="alert" className="text-body-sm text-error">
                {error}
              </p>
            )}
            <div className="flex gap-3">
              <Button type="button" variant="outline" fullWidth className="min-w-0 rounded-xl px-0" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" fullWidth className="min-w-0 rounded-xl px-0" disabled={busy || !email.trim()}>
                {busy ? "Sending…" : "Send code"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <OtpInput value={code} onChange={setCode} disabled={busy} onComplete={(value) => void confirm(value)} />
            {debugCode && (
              <p className="text-body-sm text-grey-600">
                Development only — the code is <strong>{debugCode}</strong>
              </p>
            )}
            {error && (
              <p role="alert" className="text-body-sm text-error">
                {error}
              </p>
            )}
            <div className="flex w-full gap-3">
              <Button
                variant="outline"
                fullWidth
                className="min-w-0 rounded-xl px-0"
                onClick={() => {
                  setSent(false);
                  setCode("");
                  setError(null);
                }}
              >
                Change address
              </Button>
              <Button fullWidth className="min-w-0 rounded-xl px-0" disabled={busy || code.length !== 6} onClick={() => void confirm()}>
                {busy ? "Confirming…" : "Confirm"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

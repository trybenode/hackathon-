"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { OtpInput } from "@/components/guarantor/OtpInput";
import { OnboardingHero } from "@/components/verification/OnboardingHero";
import { Button, Input, Switch } from "@/components/ui";
import { ApiError, requestLoginCode, verifyLoginCode } from "@/lib/guarantor";

const RESEND_COOLDOWN_SECONDS = 60;

function MailCheckIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20 12V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h8" />
      <path d="m3.5 7 8.5 6 8.5-6" />
      <circle cx="18" cy="17.5" r="3.5" />
      <path d="m16.5 17.5 1 1 2-2" />
    </svg>
  );
}

/**
 * "Get started with our API": a developer's work email and a one-time code.
 * Verifying opens the account and the developer dashboard.
 */
export function DeveloperSignUp() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  /** Shown only in development, where the API returns the code. */
  const [debugCode, setDebugCode] = useState<string | null>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function sendCode() {
    setBusy(true);
    setError(null);
    try {
      const result = await requestLoginCode(email.trim());
      setDebugCode(result.debug_code);
      setCodeSent(true);
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not send a code. Check the address.");
    } finally {
      setBusy(false);
    }
  }

  async function verify(value = code) {
    if (value.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      await verifyLoginCode(email.trim(), value, "developer");
      router.push("/developer");
    } catch (cause) {
      setCode("");
      setError(cause instanceof ApiError ? cause.message : "Could not verify that code.");
      setBusy(false);
    }
  }

  function submitEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (agreed && email.trim()) void sendCode();
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col">
      <OnboardingHero />

      {!codeSent ? (
        <form onSubmit={submitEmail} className="flex flex-1 flex-col gap-6 px-6 pt-10 pb-10">
          <div className="flex flex-col gap-2 text-center">
            <h1 className="text-body-lg font-semibold text-grey-900">Get started with our API</h1>
            <p className="text-body-sm text-grey-900">
              Create your developer account to access our trust infrastructure API
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Input
              name="email"
              type="email"
              label="Work Email Address"
              placeholder="Input text"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <p className="text-body-sm text-grey-600">We&rsquo;ll send a one-time verification code to this email</p>
          </div>

          <Switch
            checked={agreed}
            onChange={setAgreed}
            label={
              <span className="text-body-sm text-grey-900">
                I agree to the{" "}
                <a href="/terms" className="text-primary-400">
                  Terms and condition
                </a>
              </span>
            }
          />

          {error && (
            <p role="alert" className="text-body-sm text-error">
              {error}
            </p>
          )}

          <Button
            type="submit"
            size="lg"
            disabled={!agreed || !email.trim() || busy}
            className="mt-auto self-center rounded-xl px-12 text-body-lg font-semibold"
          >
            {busy ? "Sending…" : "Continue"}
          </Button>
        </form>
      ) : (
        <div className="flex flex-1 flex-col items-center gap-6 px-6 pt-10 pb-10 text-center">
          <div className="flex flex-col items-center gap-2">
            <span className="text-grey-900">
              <MailCheckIcon />
            </span>
            <h1 className="text-body-lg font-semibold text-grey-900">Check your email</h1>
            <p className="text-body-sm text-grey-900">Enter the 6-digit code sent to your email address</p>
          </div>

          <OtpInput value={code} onChange={setCode} disabled={busy} onComplete={(value) => void verify(value)} />

          <p className="text-body-sm text-grey-600">
            Didn&rsquo;t receive code?{" "}
            <button
              type="button"
              onClick={sendCode}
              disabled={busy || cooldown > 0}
              className="text-primary-500 disabled:text-grey-400"
            >
              {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend"}
            </button>
          </p>

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

          <Button
            size="lg"
            disabled={code.length !== 6 || busy}
            onClick={() => void verify()}
            className="rounded-xl px-10 text-body-lg font-semibold"
          >
            {busy ? "Verifying…" : "Verify email"}
          </Button>

          <p className="text-body-sm text-grey-600">
            Wrong email address?{" "}
            <button
              type="button"
              className="underline"
              onClick={() => {
                setCodeSent(false);
                setCode("");
                setError(null);
              }}
            >
              Go back
            </button>
          </p>
        </div>
      )}
    </main>
  );
}

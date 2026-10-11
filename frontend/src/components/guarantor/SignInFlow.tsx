"use client";

import Image from "next/image";
import { LanguageSelector, useLanguage } from "@/components/history/LanguageProvider";
import { workerCopy } from "@/lib/workerLanguage";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { OtpInput } from "@/components/guarantor/OtpInput";
import { Button, Input } from "@/components/ui";
import { ApiError, landingPathFor, requestLoginCode, verifyLoginCode } from "@/lib/guarantor";

const RESEND_COOLDOWN_SECONDS = 60;

export function SignInFlow({
  /** Where to go once signed in; without it, the account's roles decide. */
  redirectTo,
  /** Pre-fills the address the instrument was sent to. */
  defaultEmail = "",
}: {
  redirectTo?: string;
  defaultEmail?: string;
}) {
  const router = useRouter();
  const { language } = useLanguage();
  const workerMode = redirectTo === "/worker" || !!redirectTo?.startsWith("/worker/");
  const w = (text: string) => workerMode ? workerCopy(language, text) : text;
  const [email, setEmail] = useState(defaultEmail);
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
      setError(
        cause instanceof ApiError ? cause.message : "Could not send a code. Check the address.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(value: string) {
    setBusy(true);
    setError(null);

    try {
      const user = await verifyLoginCode(email.trim(), value);
      router.push(redirectTo ?? landingPathFor(user));
    } catch (cause) {
      setCode("");
      setError(cause instanceof ApiError ? cause.message : "Could not verify that code.");
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!codeSent) return void sendCode();
    if (code.length === 6) return void submitCode(code);
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col">
      {workerMode && <div className="px-6 pt-4"><LanguageSelector /></div>}
      <div className="relative mt-6 aspect-[400/235] w-full overflow-hidden">
        <Image
          src="/guarantor-hero.webp"
          alt=""
          fill
          priority
          sizes="(max-width: 448px) 100vw, 448px"
          className="object-cover"
          style={{ objectPosition: "50% 37%" }}
        />
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6 px-6 pt-10 pb-10">
        <div className="flex flex-col gap-1 text-center">
          <h1 className="text-body-lg font-semibold text-grey-900">{w("Welcome")}</h1>
          <p className="text-body-sm text-grey-600">
            {w("Sign in or create an account to continue")}
          </p>
        </div>

        <Input
          name="email"
          type="email"
          label={w("Email")}
          placeholder={w("Enter your email")}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          // The address is fixed once a code has gone out; Resend re-sends it.
          readOnly={codeSent}
          required
        />

        {codeSent && (
          <section className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <h2 className="text-body-lg font-semibold text-grey-900">{w("OTP Verification")}</h2>
              <p className="text-body-sm text-grey-600">
                {w("Enter the verification code we just sent to your email")} {email.trim()}.
              </p>
            </div>

            <OtpInput value={code} onChange={setCode} disabled={busy} onComplete={submitCode} />

            <p className="text-center text-body-sm text-grey-600">
              {w("Did not receive code?")}{" "}
              <button
                type="button"
                onClick={sendCode}
                disabled={busy || cooldown > 0}
                className="text-primary-400 underline disabled:text-grey-400 disabled:no-underline"
              >
                {cooldown > 0 ? `${w("Resend in")} ${cooldown}s` : w("Resend")}
              </button>
            </p>

            {debugCode && (
              <p className="text-center text-body-sm text-grey-600">
                {w("Development only — the code is")} <span className="font-semibold">{debugCode}</span>
              </p>
            )}
          </section>
        )}

        {error && (
          <p role="alert" className="text-center text-body-sm text-error">
            {w(error)}
          </p>
        )}

        <Button
          type="submit"
          size="lg"
          className="mt-4 self-center rounded-lg px-16"
          disabled={busy || (codeSent ? code.length !== 6 : email.trim().length === 0)}
        >
          {busy ? "Please wait…" : w("Continue")}
        </Button>
      </form>
    </main>
  );
}

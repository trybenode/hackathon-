"use client";
import { useWorkerCopy } from "@/components/worker/useWorkerCopy";
import { LanguageSelector } from "@/components/history/LanguageProvider";
import Link from "next/link";
import { OnboardingHero } from "@/components/verification/OnboardingHero";
import { Button } from "@/components/ui";

const STEPS = [
  { title: "Identity verification", note: "Verify who you are" },
  { title: "Liveness check", note: "Confirm it's really you" },
  { title: "Add Guarantor", note: "Add someone who can vouch for you" },
];

/** "Verify your identity": where a new worker starts, before signing up. */
export function JoinIntro() {
  const { w } = useWorkerCopy();
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col">
      <div className="px-6 pt-4"><LanguageSelector /></div>
      <OnboardingHero />

      <div className="flex flex-1 flex-col gap-8 px-6 pt-10 pb-10">
        <div className="flex flex-col gap-2">
          <h1 className="text-body-lg font-semibold text-grey-900">{w("Verify your identity")}</h1>
          <p className="text-body-md text-grey-900">
            {w("Complete your verification to build your trusted worker profile")}</p>
        </div>

        <ol className="flex flex-col">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <div className="flex flex-col items-center">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-pill bg-primary-50 text-body-md text-grey-900">
                  {index + 1}
                </span>
                {index < STEPS.length - 1 && <span className="w-px flex-1 bg-primary-50" aria-hidden />}
              </div>
              <div className="flex flex-col gap-1 pb-7">
                <span className="text-body-md text-grey-900">{step.title}</span>
                <span className="text-xs leading-4 text-grey-600">{w(step.note)}</span>
              </div>
            </li>
          ))}
        </ol>

        <Link href="/join/sign-in" className="mt-auto self-center">
          <Button size="lg" className="rounded-xl px-10 text-body-lg font-semibold">
            {w("Continue")}</Button>
        </Link>
      </div>
    </main>
  );
}

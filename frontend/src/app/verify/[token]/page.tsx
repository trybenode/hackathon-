import { cookies } from "next/headers";
import { dictionaries, languageOf } from "@/lib/historyLanguage";
import { LanguageSelector } from "@/components/history/LanguageProvider";
import type { Metadata } from "next";
import { EvidenceSummary } from "@/components/worker/EvidenceSummary";
import { apiBaseUrl } from "@/lib/api";
import { getApiProxyOrigin } from "@/lib/serverApi";
import type { VerificationSummary } from "@/lib/portability";
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Worker verification", robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function VerificationPage({ params }: { params: Promise<{ token: string }> }) {
  const dictionary = dictionaries[languageOf((await cookies()).get("history_language")?.value)];
  const { token } = await params;
  let record: VerificationSummary | null = null;
  let message = "The current result could not be retrieved. Reconnect and retry; no fresh verification is available while offline.";
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token)) message = "This verification link is invalid.";
  else {
    try {
      const response = await fetch(`${(getApiProxyOrigin() ? `${getApiProxyOrigin()}/api/v1` : process.env.API_INTERNAL_BASE_URL ?? apiBaseUrl)}/verification/${encodeURIComponent(token)}`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
      if (response.ok) record = await response.json() as VerificationSummary;
      else if (response.status === 410) message = "This verification link has expired or been revoked. Ask the worker for a new link.";
      else if (response.status === 404) message = "This verification link is invalid. Check the link with the worker.";
    } catch { /* Render a retryable state without logging a bearer URL. */ }
  }
  return <main className="mx-auto flex w-full max-w-lg flex-col gap-6 p-6"><LanguageSelector /><header className="border-b border-stroke pb-5"><p className="text-body-sm text-info">Portable work evidence</p><h1 className="mt-1 text-h3 font-semibold text-navy-500">Worker verification</h1></header>{record ? <EvidenceSummary record={record} dictionary={dictionary} /> : <section className="rounded-xl border border-stroke p-5"><p role="status">{message}</p><a href={`/verify/${encodeURIComponent(token)}`} className="mt-4 inline-block rounded-lg border border-stroke px-5 py-3 text-info">Retry current result</a></section>}<p className="text-body-sm text-grey-600">Shared by the worker. Detailed history and identity documents are excluded. Identity verification and work-history evidence are separate checks.</p></main>;
}

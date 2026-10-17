"use client";
/** Worker verification/import status hub; declarations remain separate from scored verified evidence. */
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { featureRequest, type Grant, errorMessage } from "@/lib/portability";
import {
  getCapabilities,
  getOnboarding,
  listImports,
  submitCase,
  withdrawImport,
  type Capabilities,
  type PolicyType,
  type ImportBatch,
  type Onboarding,
  type Page,
} from "@/lib/admission";
import { getWorkerRecord } from "@/lib/workerRecord";
import {
  ReviewLanguageSelector,
  stateCopy,
  useReviewCopy,
} from "./ReviewLanguage";
import { UnsignedImportPanel } from "./UnsignedImportPanel";
export function VerificationNotice({
  onboarding,
}: {
  onboarding: Onboarding | null | undefined;
}) {
  const { t } = useReviewCopy();
  if (!onboarding) return null;
  return (
    <section className="rounded-xl border border-stroke p-4">
      <p>{stateCopy(onboarding.action, t)}</p>
      <Link className="underline" href="/worker/profile/record/verification">
        {t("verification")}
      </Link>
    </section>
  );
}
export function VerificationHub() {
  const [response, setResponse] = useState("");
  const { t, language } = useReviewCopy();
  const [clock, setClock] = useState(() => Date.now());
  const [grants, setGrants] = useState<Grant[]>([]);
  const [target, setTarget] = useState("");
  const [platformType, setPlatformType] = useState<PolicyType>("generic");
  const [grantPage, setGrantPage] = useState(1);
  const [grantPages, setGrantPages] = useState(1);
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [imports, setImports] = useState<Page<ImportBatch> | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [replacement, setReplacement] = useState<string | undefined>();
  const [rating, setRating] = useState<number | null>(null);
  const load = useCallback(async () => {
    try {
      const capabilities = await getCapabilities();
      setCaps(capabilities);
      const work: Promise<unknown>[] = [];
      if (capabilities.additional_verification_enabled)
        work.push(
          getOnboarding(target || undefined, platformType).then(setOnboarding),
        );
      if (capabilities.unsigned_imports_enabled)
        work.push(
          listImports(page).then(setImports),
          getWorkerRecord().then((r) => setRating(r.starting_rating)),
        );
      await Promise.all(work);
      setError("");
    } catch (e) {
      setOnboarding(null);
      setError(errorMessage(e));
    }
  }, [page, target, platformType]);
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 60000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    let live = true;
    void getCapabilities()
      .then(async (capabilities) => {
        if (!live) return;
        setCaps(capabilities);
        const work: Promise<unknown>[] = [];
        if (capabilities.additional_verification_enabled)
          work.push(
            getOnboarding(target || undefined, platformType).then((value) => {
              if (live) setOnboarding(value);
            }),
          );
        if (capabilities.unsigned_imports_enabled)
          work.push(
            listImports(page).then((value) => {
              if (live) setImports(value);
            }),
            getWorkerRecord().then((value) => {
              if (live) setRating(value.starting_rating);
            }),
          );
        await Promise.all(work);
      })
      .catch((e) => {
        if (live) setError(errorMessage(e));
      });
    return () => {
      live = false;
    };
  }, [page, target, platformType]);
  useEffect(() => {
    let live = true;
    void featureRequest<Page<Grant>>(
      `/me/worker/platform-grants?page=${grantPage}&size=20`,
    )
      .then((result) => {
        if (live) {
          setGrants(result.items);
          setGrantPages(result.pages);
        }
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [grantPage]);
  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="flex flex-col gap-5 p-6">
      <Link href="/worker/profile/record" className="underline">
        ←
      </Link>
      <h1 className="text-xl font-semibold">{t("verification")}</h1>
      <ReviewLanguageSelector />
      {!caps && !error && <p role="status">{t("loading")}</p>}
      <button
        type="button"
        className="min-h-11 rounded border px-4"
        disabled={busy}
        onClick={() => void load()}
      >
        {t("refresh")}
      </button>
      {error && <p role="alert">{error}</p>}
      {caps?.additional_verification_enabled && (
        <>
          <label>
            {t("platform")}
            <select
              className="block w-full rounded border p-2"
              value={target}
              disabled={busy}
              onChange={(e) => {
                setOnboarding(null);
                setTarget(e.target.value);
                setPlatformType("generic");
                setResponse("");
              }}
            >
              <option value="">{t("ourPlatform")}</option>
              {grants
                .filter(
                  (g) =>
                    !g.revoked_at &&
                    new Date(g.expires_at).getTime() > clock &&
                    g.permissions?.includes("read_history"),
                )
                .map((g) => (
                  <option key={g.id} value={g.organization_id || ""}>
                    {g.organization_name}
                  </option>
                ))}
            </select>
          </label>
          {target && (
            <label>
              {t("policyType")}
              <select
                className="block w-full rounded border p-2"
                value={platformType}
                disabled={busy}
                onChange={(e) => {
                  setOnboarding(null);
                  setResponse("");
                  setPlatformType(e.target.value as PolicyType);
                }}
              >
                {(["generic", "domestic", "ride_hailing"] as const).map(
                  (type) => (
                    <option key={type} value={type}>
                      {t(type)}
                    </option>
                  ),
                )}
              </select>
            </label>
          )}
          {grantPages > 1 && (
            <nav className="flex justify-between">
              <button
                disabled={grantPage === 1}
                onClick={() => setGrantPage((p) => p - 1)}
              >
                {t("previous")}
              </button>
              <span>
                {grantPage}/{grantPages}
              </span>
              <button
                disabled={grantPage >= grantPages}
                onClick={() => setGrantPage((p) => p + 1)}
              >
                {t("next")}
              </button>
            </nav>
          )}
        </>
      )}
      {onboarding && (
        <section className="flex flex-col gap-3 rounded-xl border p-4">
          <h2>{stateCopy(onboarding.action, t)}</h2>
          {onboarding.reason_codes.includes("REVIEW_PENDING") && (
            <p role="status">{t("pending")}</p>
          )}
          {onboarding.review_message && <p>{onboarding.review_message}</p>}
          {onboarding.requirements.map((item) => (
            <p key={item}>{stateCopy(item, t)}</p>
          ))}
          {onboarding.action === "additional_verification" && (
            <Link className="underline" href="/join/identity">
              {t("additional_verification")}
            </Link>
          )}
          {onboarding.restrictions && (
            <>
              <p>
                {t("jobs")}: {onboarding.restrictions.max_active_jobs}
              </p>
              <p>
                {t("amount")}:{" "}
                {new Intl.NumberFormat(language === "en" ? "en-NG" : language, {
                  style: "currency",
                  currency: "NGN",
                }).format(Number(onboarding.restrictions.max_job_value))}
              </p>
            </>
          )}
          {onboarding.expires_at && (
            <p>
              {t("expires")}:{" "}
              {new Intl.DateTimeFormat(language).format(
                new Date(onboarding.expires_at),
              )}
            </p>
          )}
          {onboarding.requirements.includes("supporting_information") && (
            <label>
              {t("supporting_information")}
              <textarea
                className="block w-full rounded border p-2"
                maxLength={2000}
                value={response}
                onChange={(e) => setResponse(e.target.value)}
              />
            </label>
          )}
          {onboarding.next_steps.includes("submit_review") && (
            <button
              type="button"
              className="min-h-11 rounded border px-4"
              disabled={busy}
              onClick={() =>
                void act(() =>
                  submitCase(target || undefined, response, platformType),
                )
              }
            >
              {t("caseSubmit")}
            </button>
          )}
          <p className="text-sm">{t("reviewer")}</p>
        </section>
      )}
      {rating !== null && (
        <p>
          {t("provisional")}:{" "}
          {new Intl.NumberFormat(language, { maximumFractionDigits: 2 }).format(
            rating,
          )}{" "}
          / 0.65
        </p>
      )}
      {caps?.unsigned_imports_enabled && (
        <>
          <UnsignedImportPanel
            key={replacement || "new"}
            replaces={replacement}
            onSubmitted={load}
          />
          <h2 className="font-semibold">{t("imports")}</h2>
          {imports?.items.length === 0 && <p>{t("noImports")}</p>}
          {imports?.items.map((item) => (
            <article
              key={item.id}
              className="flex flex-col gap-2 rounded-xl border p-4"
            >
              <p>
                {item.source_name} ·{" "}
                {stateCopy(
                  item.state === "approved" ? "ownership_approved" : item.state,
                  t,
                )}{" "}
                · {item.row_count}
              </p>
              {item.last_reason && <p>{item.last_reason}</p>}
              {item.state !== "withdrawn" && (
                <button
                  className="min-h-11 rounded border px-4"
                  disabled={busy}
                  onClick={() => void act(() => withdrawImport(item))}
                >
                  {t("withdraw")}
                </button>
              )}
              {item.state !== "preparing" && (
                <button
                  className="min-h-11 rounded border px-4"
                  disabled={busy}
                  onClick={() => setReplacement(item.id)}
                >
                  {t("replace")}
                </button>
              )}
            </article>
          ))}
          {imports && imports.pages > 1 && (
            <nav className="flex justify-between">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                {t("previous")}
              </button>
              <span>
                {page}/{imports.pages}
              </span>
              <button
                disabled={page >= imports.pages}
                onClick={() => setPage((p) => p + 1)}
              >
                {t("next")}
              </button>
            </nav>
          )}
        </>
      )}
      {caps &&
        !caps.additional_verification_enabled &&
        !caps.unsigned_imports_enabled && <p role="status">{t("disabled")}</p>}
    </main>
  );
}

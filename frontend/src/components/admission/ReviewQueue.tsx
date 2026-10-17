"use client";
/** Explicit-role review workbench. Ownership documents never enter the tenant onboarding queue. */
import { useCallback, useEffect, useState } from "react";
import { apiBaseUrl } from "@/lib/api";
import { errorMessage } from "@/lib/portability";
import {
  caseQueue,
  decideReview,
  getPolicy,
  ownershipDetail,
  ownershipQueue,
  reviewAccess,
  savePolicy,
  type ImportBatch,
  type ImportDetail,
  type Page,
  type Policy,
  type PolicyType,
  type ReviewCase,
  type Role,
} from "@/lib/admission";
export function ReviewQueue() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [role, setRole] = useState<Role | null>(null);
  const [mode, setMode] = useState<"ownership" | "onboarding">("onboarding");
  const [imports, setImports] = useState<Page<ImportBatch> | null>(null);
  const [cases, setCases] = useState<Page<ReviewCase> | null>(null);
  const [selected, setSelected] = useState<ImportDetail | null>(null);
  const [platformType, setPlatformType] = useState<PolicyType>("generic");
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [page, setPage] = useState(1);
  const [reason, setReason] = useState("");
  const [basis, setBasis] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    void reviewAccess()
      .then((result) => {
        setRoles(result.roles);
        setRole(result.roles[0] || null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);
  const load = useCallback(async () => {
    if (!role) return;
    try {
      if (mode === "ownership") {
        setImports(await ownershipQueue(page));
        if (selected) setSelected(await ownershipDetail(selected.batch.id));
      } else {
        setCases(await caseQueue(role, page));
        if (role.scope !== "operations")
          setPolicy(await getPolicy(role, platformType));
      }
      setUncertain(false);
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [role, mode, page, selected, platformType]);
  // Selection changes are user initiated; fetching it does not trigger a second queue load.
  useEffect(() => {
    if (!role) return;
    let live = true;
    const request =
      mode === "ownership"
        ? ownershipQueue(page).then((result) => {
            if (live) setImports(result);
          })
        : Promise.all([
            caseQueue(role, page).then((result) => {
              if (live) setCases(result);
            }),
            role.scope !== "operations"
              ? getPolicy(role, platformType).then((result) => {
                  if (live) setPolicy(result);
                })
              : Promise.resolve(),
          ]);
    void request.catch((e) => {
      if (live) setError(errorMessage(e));
    });
    return () => {
      live = false;
    };
  }, [role, mode, page, platformType]);
  async function decide(
    kind: "imports" | "onboarding-cases",
    id: string,
    version: number,
    decision: string,
  ) {
    setBusy(true);
    setError("");
    try {
      await decideReview(
        kind,
        id,
        version,
        decision,
        reason,
        kind === "imports" ? basis : undefined,
      );
      await load();
    } catch (e) {
      setError(errorMessage(e));
      setUncertain(true);
    } finally {
      setBusy(false);
    }
  }
  const current = mode === "ownership" ? imports : cases;
  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-5 p-6">
      <h1 className="text-2xl font-semibold">Verification review workbench</h1>
      <p>
        Review roles are assigned by an operator. Ownership approval does not
        verify the jobs or change the verified trust score.
      </p>
      {error && <p role="alert">{error}</p>}
      {roles.length === 0 && (
        <p>
          No reviewer roles are assigned to this account.{" "}
          <a className="underline" href="/sign-in?next=%2Freview">
            Sign in
          </a>
        </p>
      )}
      {role && (
        <>
          <label>
            Review scope
            <select
              className="ml-2 rounded border p-2"
              disabled={busy || uncertain}
              value={`${role.scope}:${role.environment}`}
              onChange={(e) => {
                setRole(
                  roles.find(
                    (r) => `${r.scope}:${r.environment}` === e.target.value,
                  ) || null,
                );
                setPage(1);
                setSelected(null);
                setMode("onboarding");
              }}
            >
              {roles.map((r) => (
                <option
                  key={`${r.scope}:${r.environment}`}
                  value={`${r.scope}:${r.environment}`}
                >
                  {r.scope} / {r.environment}
                </option>
              ))}
            </select>
          </label>
          {role.scope === "operations" && (
            <nav className="flex gap-3">
              <button
                type="button"
                disabled={busy || uncertain}
                aria-pressed={mode === "ownership"}
                onClick={() => {
                  setMode("ownership");
                  setPage(1);
                  setSelected(null);
                }}
              >
                Ownership evidence
              </button>
              <button
                type="button"
                disabled={busy || uncertain}
                aria-pressed={mode === "onboarding"}
                onClick={() => {
                  setMode("onboarding");
                  setPage(1);
                  setSelected(null);
                }}
              >
                First-party onboarding
              </button>
            </nav>
          )}
          <button
            type="button"
            className="min-h-11 rounded border p-2"
            disabled={busy}
            onClick={() => void load()}
          >
            {uncertain
              ? "Reconcile decision before retrying"
              : "Refresh review queue"}
          </button>
          <label>
            Reason shown to the worker
            <textarea
              className="block w-full rounded border p-2"
              value={reason}
              maxLength={2000}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          {mode === "ownership" ? (
            <>
              <label>
                Private ownership association checked (name alone is
                insufficient)
                <textarea
                  className="block w-full rounded border p-2"
                  value={basis}
                  maxLength={1000}
                  onChange={(e) => setBasis(e.target.value)}
                />
              </label>
              {imports?.items.map((item) => (
                <article className="rounded-xl border p-4" key={item.id}>
                  <p>
                    {item.source_name} · {item.state} · {item.row_count} rows ·
                    revision {item.version}
                  </p>
                  <button
                    className="min-h-11 underline"
                    disabled={busy}
                    onClick={() =>
                      void ownershipDetail(item.id)
                        .then(setSelected)
                        .catch((e) => setError(errorMessage(e)))
                    }
                  >
                    Inspect identity association and rows
                  </button>
                </article>
              ))}
              {selected && (
                <section className="flex flex-col gap-3 rounded-xl border p-4">
                  <h2>{selected.worker.name}</h2>
                  <p>
                    {selected.worker.email} · {selected.worker.profile_phone}
                  </p>
                  <p>
                    Identity: {selected.worker.identity} / Liveness:{" "}
                    {selected.worker.liveness}
                  </p>
                  <p className="text-sm">
                    Profile names and contact details are not ownership proof.
                    Cross-check the verified provider reference and independent
                    document/job references.
                  </p>
                  {selected.worker.identity_reference && (
                    <p className="break-all text-sm">
                      Private identity reference:{" "}
                      {selected.worker.identity_reference.provider} /{" "}
                      {selected.worker.identity_reference.reference} (
                      {new Date(
                        selected.worker.identity_reference.checked_at,
                      ).toLocaleDateString()}
                      )
                    </p>
                  )}
                  {selected.batch.document_present && (
                    <a
                      className="underline"
                      href={`${apiBaseUrl}/review/imports/${selected.batch.id}/document`}
                    >
                      Download private supporting evidence
                    </a>
                  )}
                  <ul className="max-h-64 overflow-auto">
                    {selected.batch.rows.map((r) => (
                      <li key={r.job_id}>
                        {r.job_id} · {r.date} · {r.status} ·{" "}
                        {r.source_reference}
                      </li>
                    ))}
                  </ul>
                  <div className="flex flex-wrap gap-3">
                    {[
                      "approve",
                      "request_information",
                      "decline",
                      "revoke",
                    ].map((action) => (
                      <button
                        className="min-h-11 rounded border p-2"
                        key={action}
                        disabled={
                          busy ||
                          uncertain ||
                          reason.trim().length < 10 ||
                          (action === "approve" &&
                            (basis.trim().length < 10 ||
                              selected.worker.identity !== "verified" ||
                              selected.batch.state !== "submitted"))
                        }
                        onClick={() =>
                          void decide(
                            "imports",
                            selected.batch.id,
                            selected.batch.version,
                            action,
                          )
                        }
                      >
                        {action.replaceAll("_", " ")}
                      </button>
                    ))}
                  </div>
                </section>
              )}
            </>
          ) : (
            <>
              {cases?.items.map((item) => (
                <article
                  className="flex flex-col gap-3 rounded-xl border p-4"
                  key={item.id}
                >
                  <h2>{item.display_name}</h2>
                  <p>
                    {item.state} · {item.platform_type} · revision{" "}
                    {item.version} · {item.onboarding?.action}
                  </p>
                  <p>{item.onboarding?.requirements.join(", ")}</p>
                  <p>
                    Identity: {item.verification.identity}; liveness:{" "}
                    {item.verification.liveness}; guarantor:{" "}
                    {item.verification.guarantor}
                  </p>
                  <p>
                    Verified assessment: {item.assessment.band}; confidence:{" "}
                    {item.assessment.confidence}; score:{" "}
                    {item.assessment.score ?? "unknown"}
                  </p>
                  <p>{item.assessment.explanation_summary}</p>
                  {item.worker_response && (
                    <p>Worker response: {item.worker_response}</p>
                  )}
                  <p>
                    Ownership-reviewed unverified records:{" "}
                    {item.provisional.count}; provisional rating:{" "}
                    {item.provisional.rating ?? "unknown"}
                  </p>
                  {item.last_reason && <p>{item.last_reason}</p>}
                  <div className="flex flex-wrap gap-3">
                    {[
                      ...(role.scope === "operations" ? [] : ["approve"]),
                      "approve_limited",
                      "request_information",
                      "decline",
                      "revoke",
                    ].map((action) => (
                      <button
                        type="button"
                        className="min-h-11 rounded border p-2"
                        key={action}
                        disabled={
                          busy ||
                          uncertain ||
                          reason.trim().length < 10 ||
                          (action !== "revoke" &&
                            (item.state !== "pending" ||
                              item.onboarding?.action !== "manual_review"))
                        }
                        onClick={() =>
                          void decide(
                            "onboarding-cases",
                            item.id,
                            item.version,
                            action,
                          )
                        }
                      >
                        {action.replaceAll("_", " ")}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </>
          )}
          {current && current.pages > 1 && (
            <nav className="flex justify-between">
              <button
                disabled={page === 1 || busy || uncertain}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span>
                {page}/{current.pages}
              </span>
              <button
                disabled={page >= current.pages || busy || uncertain}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </nav>
          )}
          {mode === "onboarding" && role.scope !== "operations" && (
            <label>
              Policy type
              <select
                className="ml-2 rounded border p-2"
                disabled={busy || uncertain}
                value={platformType}
                onChange={(e) => {
                  setPolicy(null);
                  setPlatformType(e.target.value as PolicyType);
                }}
              >
                {["generic", "domestic", "ride_hailing"].map((type) => (
                  <option key={type} value={type}>
                    {type.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
          )}
          {mode === "onboarding" && role.scope !== "operations" && policy && (
            <form
              className="flex flex-col gap-3 rounded-xl border p-4"
              onSubmit={(e) => {
                e.preventDefault();
                setBusy(true);
                void savePolicy(role, policy, platformType)
                  .then(setPolicy)
                  .then(() => load())
                  .catch((e) => {
                    setError(errorMessage(e));
                    setUncertain(true);
                  })
                  .finally(() => setBusy(false));
              }}
            >
              <h2 className="font-semibold">
                {platformType.replaceAll("_", " ")} onboarding policy · version{" "}
                {policy.version}
              </h2>
              <p>
                Changes invalidate old case approvals. External platforms must
                enforce returned restrictions themselves.
              </p>
              <fieldset
                disabled={busy || uncertain}
                className="flex flex-col gap-3"
              >
                {(["enabled", "allow_limited", "allow_approved"] as const).map(
                  (key) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={policy.settings[key]}
                        onChange={(e) =>
                          setPolicy({
                            ...policy,
                            settings: {
                              ...policy.settings,
                              [key]: e.target.checked,
                            },
                          })
                        }
                      />
                      {key.replaceAll("_", " ")}
                    </label>
                  ),
                )}
                <label>
                  Approval days
                  <input
                    type="number"
                    min={1}
                    max={90}
                    value={policy.settings.approval_days}
                    onChange={(e) =>
                      setPolicy({
                        ...policy,
                        settings: {
                          ...policy.settings,
                          approval_days: Number(e.target.value),
                        },
                      })
                    }
                  />
                </label>
                <label>
                  Maximum active jobs
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={policy.settings.restrictions.max_active_jobs}
                    onChange={(e) =>
                      setPolicy({
                        ...policy,
                        settings: {
                          ...policy.settings,
                          restrictions: {
                            ...policy.settings.restrictions,
                            max_active_jobs: Number(e.target.value),
                          },
                        },
                      })
                    }
                  />
                </label>
                <label>
                  Maximum job value (NGN)
                  <input
                    type="number"
                    min={1}
                    value={policy.settings.restrictions.max_job_value}
                    onChange={(e) =>
                      setPolicy({
                        ...policy,
                        settings: {
                          ...policy.settings,
                          restrictions: {
                            ...policy.settings.restrictions,
                            max_job_value: e.target.value,
                          },
                        },
                      })
                    }
                  />
                </label>
                <button className="min-h-11 rounded border p-2" type="submit">
                  Save policy
                </button>
              </fieldset>
            </form>
          )}
        </>
      )}
    </main>
  );
}

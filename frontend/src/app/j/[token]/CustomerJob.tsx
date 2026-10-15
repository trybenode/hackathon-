"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { DisputeDialog } from "@/components/jobs/DisputeDialog";
import { ESCROW_CODE_LENGTH, EscrowCodeInput } from "@/components/jobs/EscrowCodeInput";
import { jobProgress } from "@/components/jobs/jobProgress";
import { ReportIssueDialog } from "@/components/jobs/ReportIssueDialog";
import { StarRating } from "@/components/jobs/StarRating";
import { ShieldIcon } from "@/components/worker/icons";
import { ScoreRing } from "@/components/worker/ScoreRing";
import { Timeline } from "@/components/worker/Timeline";
import { TrustBandBadge } from "@/components/worker/TrustBandBadge";
import { WorkerDialog } from "@/components/worker/WorkerDialog";
import { BellIcon, Button, DotIcon, Input, NigeriaFlagIcon } from "@/components/ui";
import { BRAND_NAME } from "@/lib/brand";
import { cn } from "@/lib/cn";
import {
  CUSTOMER_ISSUE_REASONS,
  getCustomerJob,
  releasePayment,
  reportCustomerIssue,
  startPayment,
  type CustomerJob as Job,
} from "@/lib/customerJobs";
import { ApiError } from "@/lib/guarantor";
import { formatClock, formatDayMonthYear, formatNaira, initialsOf } from "@/lib/workerFormat";
import { shortName } from "@/lib/workerRecord";

/** Payscrow's own site; their escrow terms live there. */
const ESCROW_TERMS_URL = "https://payscrow.net";

const STATUS: Record<Job["stage"], { label: string; dot: string }> = {
  awaiting_customer: { label: "Not booked", dot: "text-grey-400" },
  awaiting_payment: { label: "Awaiting payment", dot: "text-warning" },
  held: { label: "In progress", dot: "text-info" },
  awaiting_confirmation: { label: "Completed", dot: "text-success" },
  disputed: { label: "In dispute", dot: "text-orange" },
  released: { label: "Paid", dot: "text-success" },
  refunded: { label: "Refunded", dot: "text-grey-800" },
};

function Header({ token }: { token: string }) {
  return (
    <header className="flex items-center justify-between border-b border-stroke px-6 pt-8 pb-5">
      <span className="text-body-lg font-semibold text-grey-900">{BRAND_NAME}</span>
      <Link href={`/j/${token}/notifications`} aria-label="Notifications" className="text-grey-900">
        <BellIcon width={22} height={22} />
      </Link>
    </header>
  );
}

function money(value: string | number) {
  return formatNaira(Number(value));
}

/** Steps 2-3: "You're about to hire...", the job, and the customer's details. */
function HireIntro({ job, token }: { job: Job; token: string }) {
  const worker = shortName(job.worker.name);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const digits = phone.replace(/\D/g, "").replace(/^234/, "").replace(/^0/, "");
  const ready = name.trim().length > 1 && /.+@.+\..+/.test(email) && digits.length === 10;

  async function proceed(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const { payment_link } = await startPayment(token, {
        name: name.trim(),
        email: email.trim(),
        phone: `+234${digits}`,
      });
      // Payscrow hosts the checkout and sends the customer back here after.
      window.location.assign(payment_link);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not start the payment. Try again.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={proceed} className="flex flex-col gap-6 px-6 pt-4 pb-8">
      <p className="text-xs leading-4 text-grey-900">
        You are about to hire {worker} for {job.title.toLowerCase()}
      </p>

      <div className="flex items-center gap-4">
        <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-pill bg-primary-500 text-body-lg font-medium text-white">
          {initialsOf(job.worker.name)}
        </span>
        <span className="flex flex-1 flex-col">
          <span className="text-body-lg text-grey-900">{worker}</span>
          <span className="text-body-sm text-grey-600">{job.worker.role ?? ""}</span>
        </span>
        <TrustBandBadge band={job.worker.band} />
      </div>

      <div className="flex items-center gap-4 rounded-lg bg-primary-25 p-3">
        <ScoreRing score={job.worker.score} size={68} thickness={7} />
        <div className="flex flex-col gap-1.5">
          <p className="text-body-md font-semibold text-grey-900">Trust Score</p>
          <p className="text-xs leading-5 text-grey-900">Based on verified work history and performance</p>
        </div>
      </div>

      <dl className="flex flex-col rounded-lg border border-stroke">
        {[
          ["Job Title", job.title],
          ["Address", job.address ?? "—"],
          [
            "Date & Time",
            job.scheduled_at ? `${formatDayMonthYear(job.scheduled_at)}\n${formatClock(job.scheduled_at)}` : "—",
          ],
          ["Price", money(job.amount)],
          ...(Number(job.premium) > 0 ? [["Job protection", money(job.premium)]] : []),
        ].map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-4 border-b border-stroke px-3 py-4 last:border-b-0">
            <dt className="text-body-sm text-grey-900">{label}</dt>
            <dd className="text-right text-body-sm whitespace-pre-line text-grey-900">{value}</dd>
          </div>
        ))}
      </dl>
      {Number(job.premium) > 0 && (
        <p className="-mt-3 text-xs leading-4 text-grey-600">
          Job protection is micro-insurance for this job, paid on top of the price. Payscrow&rsquo;s escrow
          fee is added at checkout.
        </p>
      )}

      <section className="flex flex-col gap-4 rounded-lg border border-stroke p-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-body-md font-semibold text-grey-900">Your details</h2>
          <p className="text-xs leading-4 text-grey-900">
            So we can send your receipt and keep you updated on the job
          </p>
        </div>
        <Input label="Name" placeholder="Input text" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} />
        <Input
          label="Email"
          type="email"
          placeholder="Input text"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input
          label="Phone Number"
          type="tel"
          inputMode="tel"
          placeholder="Input your phone"
          autoComplete="tel-national"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          leadingIcon={<span className="text-body-sm text-grey-600">+234</span>}
          trailingIcon={<NigeriaFlagIcon />}
        />
      </section>

      <div className="flex gap-3">
        <ShieldIcon className="mt-0.5 shrink-0 text-grey-900" />
        <div className="flex flex-col gap-1">
          <p className="text-body-sm text-grey-900">Your payment is held securely</p>
          <p className="text-xs leading-4 text-grey-900">
            Your money will be held securely in escrow by Payscrow, under its terms until the agreed release
            process is completed. {worker.split(" ")[0]} is not paid before that.
          </p>
        </div>
      </div>
      <a
        href={ESCROW_TERMS_URL}
        target="_blank"
        rel="noreferrer"
        className="-mt-3 self-end text-xs text-primary-400 underline"
      >
        Read escrow terms
      </a>

      {error && (
        <p role="alert" className="text-body-sm text-error">
          {error}
        </p>
      )}

      <Button
        type="submit"
        size="lg"
        disabled={!ready || busy}
        className="w-56 self-center rounded-xl px-0 text-body-lg font-semibold"
      >
        {busy ? "Opening Payscrow…" : "Proceed to Payment"}
      </Button>
    </form>
  );
}

/** Step 7: the code Payscrow emailed, and a required one-tap rating. */
function ReleaseDialog({
  job,
  token,
  open,
  onClose,
  onReleased,
}: {
  job: Job;
  token: string;
  open: boolean;
  onClose: () => void;
  onReleased: (job: Job) => void;
}) {
  const [code, setCode] = useState("");
  const [rating, setRating] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const firstName = shortName(job.worker.name).split(" ")[0];
  const ready = code.length === ESCROW_CODE_LENGTH && rating > 0;

  async function release() {
    setBusy(true);
    setError(null);
    try {
      onReleased(await releasePayment(token, code, rating));
      onClose();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not release the payment. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkerDialog open={open} onClose={onClose} label="Enter your code">
      <div className="flex flex-col gap-5">
        <h2 className="text-body-md font-semibold text-grey-900">Enter your code</h2>
        <p className="text-body-sm text-grey-600">Enter the escrow code Payscrow emailed you when you paid.</p>
        <EscrowCodeInput value={code} onChange={setCode} disabled={busy} />

        <div className="flex flex-col gap-3 rounded-lg border border-stroke p-4">
          <p className="text-body-sm text-grey-900">How was your job with {firstName}?</p>
          <StarRating value={rating} onChange={setRating} label={`Rate your job with ${firstName}`} />
        </div>

        <p className="text-xs leading-4 text-grey-600">Only release once the job is done.</p>

        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}

        <div className="flex gap-4">
          <Button variant="outline" size="lg" fullWidth className="min-w-0 rounded-xl px-0" onClick={onClose}>
            Cancel
          </Button>
          <Button size="lg" fullWidth disabled={!ready || busy} className="min-w-0 rounded-xl px-0" onClick={release}>
            {busy ? "Releasing…" : "Release payment"}
          </Button>
        </div>
      </div>
    </WorkerDialog>
  );
}

/** Steps 4-8 and the dispute branch: the shared job page with its trail. */
function JobStatus({ job, token, onChange }: { job: Job; token: string; onChange: (job: Job) => void }) {
  const [releasing, setReleasing] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [viewingDispute, setViewingDispute] = useState(false);
  const status = STATUS[job.stage];
  const worker = shortName(job.worker.name);
  const canReport = job.stage === "held" || job.stage === "awaiting_confirmation";

  return (
    <div className="flex flex-col">
      <section className="flex items-start justify-between gap-3 border-b border-stroke px-6 py-5">
        <div className="flex flex-col gap-1">
          <p className="text-body-md text-grey-900">{job.title}</p>
          <p className="text-body-sm text-grey-900">
            {worker}
            {job.address ? ` · ${job.address}` : ""}
          </p>
        </div>
        <span className="flex shrink-0 items-center gap-1.5 text-body-sm text-grey-900">
          <DotIcon className={cn("shrink-0", status.dot)} />
          {status.label}
        </span>
      </section>

      <div className="flex flex-col gap-6 px-6 pt-8 pb-8">
        <section className="flex flex-col gap-4">
          <h2 className="text-body-md font-semibold text-grey-900">Job Progress</h2>
          <Timeline steps={jobProgress(job, "customer", job.worker.name)} />
        </section>

        {job.stage === "awaiting_confirmation" && job.confirm_by && (
          <p className="text-xs leading-4 text-grey-900">
            Please release or report a problem by {formatDayMonthYear(job.confirm_by)}, {formatClock(job.confirm_by)}.
            After that a dispute opens; the payment is never released without your code.
          </p>
        )}

        <section className="flex flex-col gap-2 rounded-lg bg-primary-25 p-4">
          <h2 className="flex items-center gap-2 text-body-md font-medium text-grey-900">
            <ShieldIcon className="text-info" />
            Payment Protected
          </h2>
          <p className="pl-7 text-body-md font-semibold text-grey-900">{money(job.amount)}</p>
          <p className="pl-7 text-xs leading-4 text-grey-900">
            {job.stage === "released"
              ? `Released to ${worker.split(" ")[0]}. Thank you for your rating.`
              : job.stage === "refunded"
                ? "Refunded to you"
                : job.stage === "awaiting_payment"
                  ? "Held securely once your payment is confirmed"
                  : "Held securely until job is confirmed"}
          </p>
        </section>

        <div className="flex flex-col items-center gap-3">
          {job.stage === "awaiting_payment" && job.payment_link && (
            <a href={job.payment_link} className="w-56">
              <Button size="lg" fullWidth className="rounded-xl px-0 text-body-lg font-semibold">
                Continue to payment
              </Button>
            </a>
          )}
          {job.stage === "awaiting_confirmation" && (
            <Button size="lg" className="w-56 rounded-xl px-0 text-body-lg font-semibold" onClick={() => setReleasing(true)}>
              Enter Code
            </Button>
          )}
          {canReport && (
            <Button
              variant="outline"
              size="lg"
              className="w-56 rounded-xl px-0 text-body-lg font-semibold"
              onClick={() => setReporting(true)}
            >
              Report an issue
            </Button>
          )}
          {job.dispute && (
            <Button
              variant="outline"
              size="lg"
              className="w-56 rounded-xl px-0 text-body-lg font-semibold"
              onClick={() => setViewingDispute(true)}
            >
              View dispute
            </Button>
          )}
        </div>
      </div>

      <ReleaseDialog job={job} token={token} open={releasing} onClose={() => setReleasing(false)} onReleased={onChange} />
      <ReportIssueDialog
        open={reporting}
        onClose={() => setReporting(false)}
        reasons={CUSTOMER_ISSUE_REASONS}
        onSubmit={async (reason, complaint, evidence) => {
          onChange(await reportCustomerIssue(token, reason, complaint, evidence));
        }}
      />
      {job.dispute && (
        <DisputeDialog dispute={job.dispute} open={viewingDispute} onClose={() => setViewingDispute(false)} />
      )}
    </div>
  );
}

export function CustomerJob({ token }: { token: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCustomerJob(token)
      .then((loaded) => {
        if (!cancelled) setJob(loaded);
      })
      .catch((cause) => {
        if (cancelled) return;
        setError(
          cause instanceof ApiError && cause.status === 404
            ? "This job link is not valid. Ask the worker to send it again."
            : "Could not load this job. Try again.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col bg-white">
      <Header token={token} />
      {error && (
        <p role="alert" className="px-6 pt-8 text-body-sm text-error">
          {error}
        </p>
      )}
      {!job && !error && (
        <p role="status" className="px-6 pt-8 text-body-sm text-grey-600">
          Loading…
        </p>
      )}
      {job &&
        (job.stage === "awaiting_customer" ? (
          <HireIntro job={job} token={token} />
        ) : (
          <JobStatus job={job} token={token} onChange={setJob} />
        ))}
    </main>
  );
}

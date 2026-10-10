"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { ChevronRightIcon } from "@/components/worker/recordIcons";
import { Button, CheckIcon, ClockIcon, VerificationBadge } from "@/components/ui";
import { formatRelative } from "@/lib/format";
import { formatShortDate } from "@/lib/workerFormat";
import { RecordGate } from "@/components/worker/RecordGate";
import { useWorkerRecord } from "@/components/worker/useWorkerRecord";
import type { Credentials } from "@/lib/workerRecord";
import { GuarantorDialog } from "./GuarantorDialog";
import { ImportRecordDialog } from "./ImportRecordDialog";

function Check({ children }: { children: ReactNode }) {
  return (
    <li className="flex items-center gap-2 text-body-sm text-grey-900">
      <CheckIcon className="shrink-0 text-success" />
      {children}
    </li>
  );
}

function CredentialCard({
  title,
  checks,
  footer,
  onOpen,
}: {
  title: string;
  checks: ReactNode;
  footer: string;
  /** Makes the footer a button that opens more detail. */
  onOpen?: () => void;
}) {
  const footerText = <span className="text-xs leading-4 text-grey-900">{footer}</span>;

  return (
    <article className="flex flex-col gap-4 rounded-xl border border-stroke bg-white p-4 pt-6">
      <header className="flex items-center justify-between gap-3">
        <h2 className="text-body-md font-semibold text-grey-900">{title}</h2>
        <VerificationBadge status="verified" className="py-0.5 text-body-sm" />
      </header>
      <ul className="flex flex-col gap-1">{checks}</ul>
      <div className="border-t border-stroke pt-4 pb-2">
        {onOpen ? (
          <button
            type="button"
            onClick={onOpen}
            className="flex w-full items-center justify-between gap-3 text-left"
          >
            {footerText}
            <ChevronRightIcon width={18} height={18} className="shrink-0 text-grey-900" />
          </button>
        ) : (
          footerText
        )}
      </div>
    </article>
  );
}

/**
 * The credentials a worker carries between platforms: identity, an active
 * guarantor, and work history imported from elsewhere.
 */
export function CredentialList() {
  const router = useRouter();
  const { data, error, loading, reload } = useWorkerRecord();

  return (
    <main className="flex flex-col">
      <header className="flex items-center gap-3 border-b border-stroke px-6 pt-8 pb-5">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
        <h1 className="text-body-lg font-semibold text-grey-900">Verified Credentials</h1>
      </header>

      <RecordGate loading={loading} error={error}>
        {data && <CredentialCards credentials={data.credentials} workerId={data.worker_id} onImported={reload} />}
      </RecordGate>
    </main>
  );
}

function CredentialCards({
  credentials,
  workerId,
  onImported,
}: {
  credentials: Credentials;
  workerId: string;
  onImported: () => void;
}) {
  const [importing, setImporting] = useState(false);
  const [guarantorOpen, setGuarantorOpen] = useState(false);
  const { identity, guarantor, imported_record: importedRecord } = credentials;
  const none = !identity && !guarantor && !importedRecord;

  return (
    <>

      <div className="flex flex-col gap-8 px-6 pt-10">
        {none && <p className="text-body-sm text-grey-600">No verified credentials yet.</p>}

        {identity && (
          <CredentialCard
            title="Identity Verification"
            checks={
              <>
                {identity.nin_verified && <Check>NIN verified</Check>}
                {identity.bvn_verified && <Check>BVN verified</Check>}
              </>
            }
            footer={`Verified - ${formatShortDate(identity.verified_at)}`}
          />
        )}

        {guarantor && (
          <CredentialCard
            title="Active Guarantor"
            checks={
              <>
                <Check>Guarantor linked</Check>
                {guarantor.status === "Active" ? (
                  <Check>Agreement active</Check>
                ) : (
                  <li className="flex items-center gap-2 text-body-sm text-grey-900">
                    <ClockIcon className="shrink-0 text-grey-600" />
                    Agreement expired
                  </li>
                )}
              </>
            }
            footer={
              guarantor.status === "Active"
                ? `Activated - ${formatShortDate(guarantor.activated_at)}`
                : `Expired - ${formatShortDate(guarantor.valid_until)}`
            }
            onOpen={() => setGuarantorOpen(true)}
          />
        )}

        {importedRecord && (
          <CredentialCard
            title="Imported Work Record"
            checks={<Check>{importedRecord.verified_outcomes} verified outcomes</Check>}
            footer={`Updated - ${formatRelative(importedRecord.updated_at)}`}
          />
        )}

        <Button
          variant="outline"
          size="lg"
          className="mt-4 mb-4 w-46 self-center rounded-xl px-0 text-body-md font-semibold"
          onClick={() => setImporting(true)}
        >
          Import record
        </Button>
        <ImportRecordDialog
          workerId={workerId}
          open={importing}
          onClose={() => setImporting(false)}
          onImported={onImported}
        />
      </div>

      {guarantor && (
        <GuarantorDialog
          guarantor={guarantor}
          open={guarantorOpen}
          onClose={() => setGuarantorOpen(false)}
        />
      )}
    </>
  );
}

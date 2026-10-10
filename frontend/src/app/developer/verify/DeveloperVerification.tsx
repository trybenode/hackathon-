"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ChoiceList } from "@/components/developer/ChoiceList";
import { DocumentUpload } from "@/components/developer/DocumentUpload";
import { StepNotice } from "@/components/developer/StepNotice";
import { useDeveloper } from "@/components/developer/useDeveloper";
import { Button, Input, Modal, Select, Switch } from "@/components/ui";
import {
  BUSINESS_TYPES,
  DOCUMENT_TYPES,
  submitDeveloperBusiness,
  submitDeveloperIdentity,
} from "@/lib/developer";
import { ApiError } from "@/lib/guarantor";

type BusinessType = (typeof BUSINESS_TYPES)[number]["value"];

function message(cause: unknown, fallback: string) {
  return cause instanceof ApiError ? cause.message : fallback;
}

/**
 * "Business Verification": identity (step 1) then the registered business
 * (step 2). Submitting sends both for an operator's review.
 */
export function DeveloperVerification() {
  const router = useRouter();
  const { data, error: loadError } = useDeveloper();
  const [chosenStep, setStep] = useState<1 | 2 | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [typedName, setFullName] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState<string | null>(null);
  const [idDocument, setIdDocument] = useState<File | null>(null);

  const [businessType, setBusinessType] = useState<BusinessType>("limited_liability_company");
  const [cacDocument, setCacDocument] = useState<File | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const settled = data?.kyb_status === "under_review" || data?.kyb_status === "approved";
  // A first try with step 1 saved picks up at step 2; after a rejection both
  // steps are redone.
  const step = chosenStep ?? (!data || settled ? null : data.identity_submitted && data.kyb_status === "not_started" ? 2 : 1);
  const fullName = typedName ?? data?.full_name ?? "";

  // Under review or approved: nothing to submit.
  useEffect(() => {
    if (settled) router.replace("/developer");
  }, [settled, router]);

  async function submitIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!documentType || !idDocument) {
      setError("Choose a document type and upload the document.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await submitDeveloperIdentity(fullName.trim(), documentType, idDocument);
      setStep(2);
    } catch (cause) {
      setError(message(cause, "Could not save your identity details. Try again."));
    } finally {
      setBusy(false);
    }
  }

  async function submitBusiness(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (!cacDocument) {
      setError("Upload your CAC registration certificate.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await submitDeveloperBusiness(
        {
          business_name: String(form.get("business_name") ?? "").trim(),
          business_type: businessType,
          registration_number: String(form.get("registration_number") ?? "").trim(),
          tax_id: String(form.get("tax_id") ?? "").trim(),
        },
        cacDocument,
      );
      router.push("/developer");
    } catch (cause) {
      setError(message(cause, "Could not submit your business details. Try again."));
      setBusy(false);
    }
  }

  const failure = error ?? loadError;

  return (
    <main className="mx-auto flex w-full max-w-md flex-col px-6 pt-8 pb-10">
      <div className="flex flex-col gap-1 pb-6">
        <h1 className="text-body-lg font-semibold text-grey-900">Business Verification</h1>
        <p className="text-body-sm text-grey-900">Step {step ?? 1} of account Verification</p>
      </div>

      {step === 1 && (
        <form onSubmit={submitIdentity} className="flex flex-col gap-6">
          <StepNotice title="Verify your identity">
            Provide your personal details so we can verify your identity. Your information will be handled securely
          </StepNotice>
          <Input
            label="Full Name"
            placeholder="Input text"
            autoComplete="name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            required
          />
          <Select
            label="Select document type"
            placeholder="Select"
            options={DOCUMENT_TYPES}
            value={documentType}
            onChange={setDocumentType}
          />
          <DocumentUpload
            heading="Upload selected document"
            title="Upload identity document."
            file={idDocument}
            onChange={setIdDocument}
          />
          {failure && (
            <p role="alert" className="text-body-sm text-error">
              {failure}
            </p>
          )}
          <Button type="submit" size="lg" disabled={busy} className="self-end rounded-xl px-12">
            {busy ? "Saving…" : "Next"}
          </Button>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={submitBusiness} className="flex flex-col gap-6">
          <StepNotice title="Verify your business">
            Provide your registered business details and supporting documents to unlock API access after
            verification approval
          </StepNotice>
          <Input
            name="business_name"
            label="Registered Business Name"
            placeholder="Enter name as registered with CAC"
            autoComplete="organization"
            required
          />
          <ChoiceList legend="Business type" options={BUSINESS_TYPES} value={businessType} onChange={setBusinessType} />
          <Input
            name="registration_number"
            label="Registration Number"
            placeholder="Enter your registration number"
            required
          />
          <Input name="tax_id" label="Tax Identification Number" placeholder="Enter your business TIN" required />
          <div className="border-t border-stroke" />
          <DocumentUpload
            heading="Upload CAC registration document"
            title="Upload registration certificate"
            file={cacDocument}
            onChange={setCacDocument}
          />
          <Switch
            checked={confirmed}
            onChange={setConfirmed}
            label={
              <span className="text-body-sm text-grey-900">
                I confirm that the information provided is accurate and acknowledge the privacy notice.
              </span>
            }
          />
          <a href="/privacy" className="self-end text-body-sm text-primary-400 underline">
            Read our Privacy Policy
          </a>
          {failure && (
            <p role="alert" className="text-body-sm text-error">
              {failure}
            </p>
          )}
          <Button type="submit" size="lg" disabled={busy || !confirmed} className="self-end rounded-xl px-12">
            Submit
          </Button>
        </form>
      )}

      <Modal open={busy && step === 2} title="Verifying your identity…" hideTitle>
        <span className="h-12 w-12 animate-spin rounded-pill border-4 border-primary-100 border-t-primary-400" />
        <h2 className="text-h3 text-grey-900">Verifying your identity...</h2>
        <p className="text-body-md text-grey-600">
          We&rsquo;re securely checking your details. This should only take a moment
        </p>
      </Modal>
    </main>
  );
}

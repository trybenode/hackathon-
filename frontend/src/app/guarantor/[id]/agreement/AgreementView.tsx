"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useGuarantee } from "@/components/dashboard/useGuarantee";
import { Button } from "@/components/ui";
import { ArrowLeftIcon } from "@/components/worker/icons";
import { downloadAgreement } from "@/lib/guarantor";

export function AgreementView({ instrumentId }: { instrumentId: string }) {
  const router = useRouter();
  const { data, error, loading } = useGuarantee(instrumentId);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function download() {
    setDownloading(true);
    setDownloadError(null);
    try {
      const { blob, filename } = await downloadAgreement(instrumentId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError("Could not download the agreement. Try again.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col">
      <header className="flex items-center border-b border-stroke px-6 pt-6 pb-4">
        <button type="button" aria-label="Back" onClick={() => router.back()} className="text-grey-900">
          <ArrowLeftIcon />
        </button>
      </header>

      <div className="flex flex-1 flex-col gap-4 px-6 pt-8">
        <h1 className="text-body-md font-semibold text-grey-900">Agreement</h1>

        {loading && (
          <p role="status" className="text-body-sm text-grey-600">
            Loading…
          </p>
        )}
        {error && (
          <p role="alert" className="text-body-sm text-error">
            {error}
          </p>
        )}

        {data && (
          <div className="flex flex-col px-2 text-justify text-body-md leading-6 text-grey-900">
            {data.agreement.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        )}
      </div>

      {data && (
        <div className="flex flex-col items-center gap-2 px-6 pt-10 pb-12">
          {downloadError && (
            <p role="alert" className="text-body-sm text-error">
              {downloadError}
            </p>
          )}
          <Button
            variant="outline"
            size="lg"
            className="w-50 rounded-xl px-0 text-body-md font-semibold"
            disabled={downloading}
            onClick={download}
          >
            {downloading ? "Downloading…" : "Download"}
          </Button>
        </div>
      )}
    </main>
  );
}

"use client";

import { FileDropzone, FileItem } from "@/components/ui";

/** Accepted by the document store: PDF and images, up to 10 MB. */
const ACCEPT = "image/jpeg,image/png,application/pdf";
const HINT = "JPEG, PNG and PDF formats, up to 10 MB.";

/** A heading, the dashed drop area, and the chosen file once picked. */
export function DocumentUpload({
  heading,
  title,
  file,
  onChange,
}: {
  heading: string;
  title: string;
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-body-md font-medium text-grey-800">{heading}</h2>
      <FileDropzone title={title} hint={HINT} accept={ACCEPT} onFiles={(files) => onChange(files[0] ?? null)} />
      {file && (
        <FileItem name={file.name} size={file.size} loaded={file.size} status="completed" onRemove={() => onChange(null)} />
      )}
    </div>
  );
}

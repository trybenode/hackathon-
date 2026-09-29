"use client";

import { useState } from "react";
import { FileDropzone, FileItem } from "@/components/ui";

const TOTAL = 122880;

export function UploadDemo() {
  const [picked, setPicked] = useState<string[]>([]);

  return (
    <div className="flex flex-col gap-8">
      <div className="grid max-w-4xl gap-6 md:grid-cols-2">
        <FileDropzone multiple onFiles={(files) => setPicked(files.map((file) => file.name))} />
        <FileDropzone disabled />
      </div>

      {picked.length > 0 && (
        <p className="text-body-sm text-grey-600">Picked: {picked.join(", ")}</p>
      )}

      <div className="flex max-w-md flex-col gap-3">
        <FileItem name="example.pdf" loaded={72000} size={TOTAL} status="uploading" onCancel={() => {}} />
        <FileItem name="example.pdf" loaded={TOTAL} size={TOTAL} status="completed" onRemove={() => {}} />
        <FileItem name="example.pdf" size={TOTAL} status="failed" onRemove={() => {}} onRetry={() => {}} />
      </div>
    </div>
  );
}

"use client";

import { useRef } from "react";
import { cn } from "@/lib/cn";

/** "Upload utility bill": a file button with the chosen file's name beside it. */
export function UtilityBillInput({ file, onChange }: { file: File | null; onChange: (file: File | null) => void }) {
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-col gap-2">
      <span className="text-body-sm font-medium text-grey-900">Upload utility bill</span>
      <div className="flex items-stretch rounded-md border border-stroke">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className={cn(
            "shrink-0 rounded-l-md border border-primary-300 px-4 py-3 text-body-sm font-medium",
            "text-grey-900 outline-none focus-visible:ring-2 focus-visible:ring-primary-300",
          )}
        >
          Upload file
        </button>
        <span
          className={cn(
            "flex min-w-0 flex-1 items-center truncate px-4 text-body-sm",
            file ? "text-grey-900" : "text-grey-400",
          )}
        >
          {file?.name ?? "File name"}
        </span>
      </div>
      <input
        ref={fileRef}
        type="file"
        name="utility_bill"
        accept="image/jpeg,image/png,application/pdf"
        className="hidden"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      <p className="text-body-sm text-grey-600">
        We&rsquo;ll never share your details. See our Privacy Policy.
      </p>
    </div>
  );
}

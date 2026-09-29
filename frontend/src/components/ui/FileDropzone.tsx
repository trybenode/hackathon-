"use client";

import { useRef, useState, type DragEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Button } from "./Button";
import { CloudUploadIcon } from "./icons";

export type FileDropzoneProps = {
  /** Called with the picked or dropped files. */
  onFiles?: (files: File[]) => void;
  title?: ReactNode;
  /** Line under the title, e.g. the accepted formats and size limit. */
  hint?: ReactNode;
  buttonLabel?: string;
  /** Passed to the file input, e.g. "image/jpeg,image/png,application/pdf,video/mp4". */
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  className?: string;
};

export function FileDropzone({
  onFiles,
  title = "Choose a file or drag & drop it here.",
  hint = "JPEG, PNG, PDF, and MP4 formats, up to 50 MB.",
  buttonLabel = "Browse File",
  accept,
  multiple = false,
  disabled = false,
  className,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const emit = (list: FileList | null) => {
    if (!list?.length) return;
    onFiles?.(Array.from(list));
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!disabled) emit(event.dataTransfer.files);
  };

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "flex min-h-52 flex-col items-center justify-center gap-1 rounded-lg border border-dashed px-8 py-10 text-center transition-colors",
        disabled
          ? "border-grey-200 bg-grey-200 text-grey-400"
          : dragging
            ? "border-primary-400 bg-primary-50"
            : "border-grey-400 bg-white",
        className,
      )}
    >
      <CloudUploadIcon className={cn("mb-3", disabled ? "text-grey-400" : "text-grey-900")} />
      <p className={cn("text-body-md font-semibold", !disabled && "text-grey-900")}>{title}</p>
      {hint && <p className={cn("text-body-sm", !disabled && "text-grey-600")}>{hint}</p>}
      <Button
        size="sm"
        variant="outline"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="mt-6 rounded-md"
      >
        {buttonLabel}
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        className="hidden"
        onChange={(event) => {
          emit(event.target.files);
          // Allow re-picking the same file.
          event.target.value = "";
        }}
      />
    </div>
  );
}

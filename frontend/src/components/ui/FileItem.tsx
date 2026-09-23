"use client";

import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";
import { ProgressBar } from "./ProgressBar";
import { CheckCircleIcon, CloseIcon, ErrorCircleIcon, SpinnerIcon, TrashIcon } from "./icons";

export type FileStatus = "uploading" | "completed" | "failed";

const extensionColors: Record<string, string> = {
  pdf: "bg-error",
  jpg: "bg-info",
  jpeg: "bg-info",
  png: "bg-info",
  mp4: "bg-navy-400",
};

function FileTypeIcon({ name }: { name: string }) {
  const extension = name.split(".").pop()?.toLowerCase() ?? "";
  const label = extension.slice(0, 4).toUpperCase();

  return (
    <span className="relative flex h-10 w-8 shrink-0 items-end justify-center">
      <svg viewBox="0 0 32 40" className="absolute inset-0 h-full w-full" aria-hidden>
        <path
          d="M4 2h15l9 9v27a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z"
          fill="white"
          stroke="#bdbdbd"
          strokeWidth="1.5"
        />
        <path d="M19 2.5V11h8.5" fill="none" stroke="#bdbdbd" strokeWidth="1.5" />
      </svg>
      {label && (
        <span
          className={cn(
            "relative mb-1 rounded-sm px-1 text-[8px] leading-3 font-bold text-white",
            extensionColors[extension] ?? "bg-grey-600",
          )}
        >
          {label}
        </span>
      )}
    </span>
  );
}

export type FileItemProps = {
  name: string;
  /** Bytes transferred so far. */
  loaded?: number;
  /** Total size in bytes. */
  size?: number;
  status?: FileStatus;
  /** Upload progress 0–100. Defaults to loaded/size. */
  progress?: number;
  /** Cancel (×) while uploading. */
  onCancel?: () => void;
  /** Remove (trash) once finished or failed. */
  onRemove?: () => void;
  /** Shows the "Try Again" link when the upload failed. */
  onRetry?: () => void;
  className?: string;
};

const statusLabels: Record<FileStatus, string> = {
  uploading: "Uploading ...",
  completed: "Completed",
  failed: "Failed",
};

export function FileItem({
  name,
  loaded = 0,
  size = 0,
  status = "uploading",
  progress,
  onCancel,
  onRemove,
  onRetry,
  className,
}: FileItemProps) {
  const percent = progress ?? (size > 0 ? (loaded / size) * 100 : 0);
  const failed = status === "failed";

  return (
    <div
      className={cn(
        "flex w-full items-start gap-3 rounded-lg border px-3 py-3",
        failed ? "border-error-light bg-error-light/40" : "border-grey-200 bg-white",
        className,
      )}
    >
      <FileTypeIcon name={name} />

      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <p className="truncate text-body-sm font-semibold text-grey-900">{name}</p>
        <p className="flex items-center gap-1.5 text-xs leading-4 text-grey-600">
          <span>
            {formatBytes(loaded)} of {formatBytes(size)}
          </span>
          <span aria-hidden>•</span>
          {status === "uploading" && <SpinnerIcon className="animate-spin text-primary-400" />}
          {status === "completed" && <CheckCircleIcon className="text-success" />}
          {failed && <ErrorCircleIcon className="text-error" />}
          <span className={cn(failed && "text-error")}>{statusLabels[status]}</span>
        </p>

        {status === "uploading" && <ProgressBar value={percent} tone="success" label={`Uploading ${name}`} />}

        {failed && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="self-start text-xs leading-4 font-medium text-error underline"
          >
            Try Again
          </button>
        )}
      </div>

      {status === "uploading"
        ? onCancel && (
            <button
              type="button"
              onClick={onCancel}
              aria-label={`Cancel upload of ${name}`}
              className="shrink-0 rounded-sm text-grey-600 hover:text-grey-900"
            >
              <CloseIcon />
            </button>
          )
        : onRemove && (
            <button
              type="button"
              onClick={onRemove}
              aria-label={`Remove ${name}`}
              className={cn(
                "shrink-0 rounded-sm",
                failed ? "text-error" : "text-grey-600 hover:text-grey-900",
              )}
            >
              <TrashIcon />
            </button>
          )}
    </div>
  );
}

"use client";

import { cn } from "@/lib/cn";

function Star({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden>
      <path
        d="m12 2.6 2.9 6 6.5.8-4.8 4.5 1.2 6.5L12 17.2l-5.8 3.2 1.2-6.5L2.6 9.4l6.5-.8z"
        className={cn(filled ? "fill-warning stroke-warning" : "fill-grey-200 stroke-grey-200")}
        strokeWidth="1"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** One-tap 1-5 star rating, required before the customer can release. */
export function StarRating({
  value,
  onChange,
  label,
}: {
  value: number;
  onChange: (value: number) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex justify-center gap-2">
      {[1, 2, 3, 4, 5].map((stars) => (
        <button
          key={stars}
          type="button"
          role="radio"
          aria-checked={value === stars}
          aria-label={`${stars} star${stars === 1 ? "" : "s"}`}
          onClick={() => onChange(stars)}
          className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300"
        >
          <Star filled={stars <= value} />
        </button>
      ))}
    </div>
  );
}

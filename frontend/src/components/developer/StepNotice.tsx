import type { ReactNode } from "react";

/** The grey card heading each verification step: shield, title, one line. */
export function StepNotice({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg bg-grey-50 p-3">
      <p className="flex items-center gap-2 text-body-md font-medium text-grey-900">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden>
          <path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6l-7-3Z" />
          <path d="m9 12 2 2 4-4" strokeLinecap="round" />
        </svg>
        {title}
      </p>
      <p className="text-xs leading-4 text-grey-900">{children}</p>
    </div>
  );
}

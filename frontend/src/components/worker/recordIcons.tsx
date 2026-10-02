/**
 * Purpose: Icons for the worker profile and portable record screens.
 * Dependencies: none.
 * Used by: the worker profile, portable record and share dialog.
 *
 * Kept apart from components/ui/icons.tsx for the same reason as ./icons.tsx;
 * move both into the shared set after the guarantor branch merges.
 */

import type { ComponentProps } from "react";

type IconProps = ComponentProps<"svg">;

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" {...stroke} {...props}>
      <path d="m9 5 7 7-7 7" />
    </svg>
  );
}

/** The filled green rosette beside a verified name. */
export function VerifiedIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden {...props}>
      <path
        fill="currentColor"
        d="M12 1.8 14.6 4l3.4-.3.8 3.3 2.9 1.8-1.4 3.2 1.4 3.2-2.9 1.8-.8 3.3-3.4-.3L12 22.2 9.4 20l-3.4.3-.8-3.3-2.9-1.8L3.7 12 2.3 8.8 5.2 7l.8-3.3 3.4.3z"
      />
      <path
        d="m8.2 12.2 2.6 2.6 5-5.2"
        fill="none"
        stroke="#fff"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Outlined rosette, for verified credentials. */
export function CredentialIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="M12 2.5 14.4 4.5l3.1-.3.7 3 2.7 1.7-1.3 2.9 1.3 2.9-2.7 1.7-.7 3-3.1-.3L12 21.5l-2.4-2-3.1.3-.7-3-2.7-1.7 1.3-2.9-1.3-2.9 2.7-1.7.7-3 3.1.3z" />
      <path d="m8.7 12.1 2.3 2.3 4.3-4.5" />
    </svg>
  );
}

export function ChartIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="M3 21h18M6 17v-4M10 17V9M14 17V5M18 17v-6" />
    </svg>
  );
}

export function PeopleIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 19.5a6 6 0 0 1 12 0M15.5 5.2a3.2 3.2 0 0 1 0 5.9M17.5 14.2a6 6 0 0 1 3.5 5.3" />
    </svg>
  );
}

export function WarningIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="M10.3 4.2 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9.5v4M12 16.8v.2" />
    </svg>
  );
}

export function DownloadIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="M12 3.5v11M7.5 10l4.5 4.5 4.5-4.5M4 15.5V19a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 19v-3.5" />
    </svg>
  );
}

export function ShareIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <circle cx="18" cy="5.5" r="2.5" />
      <circle cx="6" cy="12" r="2.5" />
      <circle cx="18" cy="18.5" r="2.5" />
      <path d="m8.2 10.8 7.6-4.1M8.2 13.2l7.6 4.1" />
    </svg>
  );
}

export function CopyIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" {...stroke} {...props}>
      <rect x="8" y="8" width="12" height="12" rx="2" />
      <path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8" />
    </svg>
  );
}

/** Stacked drawers, for the portable record row on Profile. */
export function RecordIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <rect x="5" y="3" width="14" height="18" rx="1.5" />
      <path d="M5 9h14M5 15h14M8.5 6h1M8.5 12h1M8.5 18h1" />
    </svg>
  );
}

/**
 * Purpose: Icons the developer screens need that the shared set lacks.
 * Dependencies: none.
 * Used by: the developer dashboard, verification and profile screens.
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

export function UserIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </svg>
  );
}

export function BuildingIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 9h4a1 1 0 0 1 1 1v11M3 21h18" />
      <path d="M8 8h3M8 12h3M8 16h3" />
    </svg>
  );
}

export function ImageIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" {...stroke} {...props}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="m4 16 4.5-4.5 3.5 3.5 2.5-2.5L20 18" />
    </svg>
  );
}

export function TickIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" {...stroke} strokeWidth={2} {...props}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}

export function BarChartIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden {...props}>
      <rect x="5" y="11" width="3.5" height="8" rx="1" />
      <rect x="10.25" y="5" width="3.5" height="14" rx="1" />
      <rect x="15.5" y="8.5" width="3.5" height="10.5" rx="1" />
    </svg>
  );
}

export function WarningIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" {...stroke} {...props}>
      <path d="M10.3 4.3 2.8 17.5A2 2 0 0 0 4.5 20.5h15a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9.5v4.5M12 17.5h.01" />
    </svg>
  );
}

export function EyeIcon({ open, ...props }: IconProps & { open: boolean }) {
  return open ? (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="M3 10c2.5 3 5.5 4.5 9 4.5s6.5-1.5 9-4.5M6.5 13l-1.5 2.5M12 14.5V17M17.5 13l1.5 2.5" />
    </svg>
  );
}

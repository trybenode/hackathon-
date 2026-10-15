/**
 * Icons the landing page needs that the shared sets lack.
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

/** A person in a circle: "For workers" and the portable record. */
export function UserCircleIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="10" r="3" />
      <path d="M6.6 18.2a6.5 6.5 0 0 1 10.8 0" />
    </svg>
  );
}

export function CodeIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="m8 7-5 5 5 5M16 7l5 5-5 5M13.5 5l-3 14" />
    </svg>
  );
}

export function InstagramIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" {...stroke} {...props}>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="0.6" fill="currentColor" />
    </svg>
  );
}

/** "Trust-Band Scoring". */
export function HandshakeIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" {...stroke} {...props}>
      <path d="m11 17 2 2a1 1 0 1 0 3-3" />
      <path d="m14 14 2.5 2.5a1 1 0 1 0 3-3l-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4" />
      <path d="m21 3 1 11h-2M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3M3 4h8" />
    </svg>
  );
}

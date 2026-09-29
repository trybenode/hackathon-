import type { ComponentProps } from "react";

type IconProps = ComponentProps<"svg">;

export function CaretDownIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden {...props}>
      <path d="M3.5 6h9L8 11z" />
    </svg>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      aria-hidden
      {...props}
    >
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  );
}

export function CheckCircleIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden {...props}>
      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm3.2 5.2-3.7 3.9a.75.75 0 0 1-1.08 0L4.8 8.4a.75.75 0 1 1 1.1-1.02l1.07 1.13 3.16-3.34a.75.75 0 1 1 1.08 1.03z" />
    </svg>
  );
}

export function ErrorCircleIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden {...props}>
      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm2.53 8.47a.75.75 0 1 1-1.06 1.06L8 9.06l-1.47 1.47a.75.75 0 0 1-1.06-1.06L6.94 8 5.47 6.53a.75.75 0 0 1 1.06-1.06L8 6.94l1.47-1.47a.75.75 0 0 1 1.06 1.06L9.06 8z" />
    </svg>
  );
}

// Magic Star and Magicpen: Iconsax "Bold" set (MIT), as used in the Figma designs.
export function MagicStarIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden {...props}>
      <path d="m17.29 4.14-.07 3.79c-.01.52.32 1.21.74 1.52l2.48 1.88c1.59 1.2 1.33 2.67-.57 3.27l-3.23 1.01c-.54.17-1.11.76-1.25 1.31l-.77 2.94c-.61 2.32-2.13 2.55-3.39.51l-1.76-2.85c-.32-.52-1.08-.91-1.68-.88l-3.34.17c-2.39.12-3.07-1.26-1.51-3.08l1.98-2.3c.37-.43.54-1.23.37-1.77L4.27 6.42c-.59-1.9.47-2.95 2.36-2.33l2.95.97c.5.16 1.25.05 1.67-.26l3.08-2.22c1.67-1.19 3-.49 2.96 1.56Z" />
      <path d="m21.44 20.47-3.03-3.03a.754.754 0 0 0-1.06 0c-.29.29-.29.77 0 1.06l3.03 3.03c.15.15.34.22.53.22s.38-.07.53-.22c.29-.29.29-.77 0-1.06Z" />
    </svg>
  );
}

export function MagicpenIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden {...props}>
      {/* Flipped horizontally to match the designs (sparkles top right). */}
      <path transform="matrix(-1 0 0 1 24 0)" d="m19.5 7.499-1.49 1.49-3-3 1.49-1.49c.42-.42.96-.62 1.5-.62s1.08.2 1.5.62c.83.83.83 2.17 0 3ZM17.31 9.7 6.5 20.5c-.83.83-2.17.83-3 0-.83-.83-.83-2.17 0-3L14.31 6.7l3 3ZM9.95 3.5l.41-1.39c.04-.13 0-.27-.09-.37-.09-.1-.25-.14-.38-.1l-1.39.41-1.39-.41c-.13-.04-.27 0-.37.09-.1.1-.13.24-.09.37l.4 1.4-.41 1.39c-.04.13 0 .27.09.37.1.1.24.13.37.09l1.4-.4 1.39.41c.04.01.07.02.11.02.1 0 .19-.04.27-.11.1-.1.13-.24.09-.37l-.41-1.4ZM5.95 9.5l.41-1.39c.04-.13 0-.27-.09-.37-.1-.1-.24-.13-.37-.09l-1.4.4-1.39-.41c-.13-.04-.27 0-.37.09-.1.1-.13.24-.09.37l.4 1.4-.41 1.39c-.04.13 0 .27.09.37.1.1.24.13.37.09l1.39-.41 1.39.41c.03.01.07.01.11.01.1 0 .19-.04.27-.11.1-.1.13-.24.09-.37l-.4-1.38ZM20.95 14.5l.41-1.39c.04-.13 0-.27-.09-.37-.1-.1-.24-.13-.37-.09l-1.39.41-1.39-.41c-.13-.04-.27 0-.37.09-.1.1-.13.24-.09.37l.41 1.39-.41 1.39c-.04.13 0 .27.09.37.1.1.24.13.37.09l1.39-.41 1.39.41c.03.01.07.01.11.01.1 0 .19-.04.27-.11.1-.1.13-.24.09-.37l-.42-1.38Z" />
    </svg>
  );
}

export function CloudUploadIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="24"
      height="24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <path d="M6.5 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 17.7 9.2 4 4 0 0 1 17.5 18" />
      <path d="M12 12v7M9.5 14.5 12 12l2.5 2.5" />
    </svg>
  );
}

export function TrashIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <path d="M2.5 4h11M6.5 4V2.8h3V4M4 4l.6 8.4a1 1 0 0 0 1 .9h4.8a1 1 0 0 0 1-.9L12 4M6.6 6.8v3.8M9.4 6.8v3.8" />
    </svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <path d="m3 8.5 3.2 3.2L13 5" />
    </svg>
  );
}

export function ExclamationIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden
      {...props}
    >
      <path d="M8 3.2v5.4M8 12.2v.6" />
    </svg>
  );
}

export function SpinnerIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden
      {...props}
    >
      <circle cx="8" cy="8" r="6" opacity="0.25" />
      <path d="M14 8a6 6 0 0 0-6-6" />
    </svg>
  );
}

export function DotIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 8 8" width="8" height="8" fill="currentColor" aria-hidden {...props}>
      <circle cx="4" cy="4" r="3" />
    </svg>
  );
}

export function AlertCircleIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden {...props}>
      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm.75 10.25a.75.75 0 0 1-1.5 0v-.5a.75.75 0 0 1 1.5 0zm0-3.5a.75.75 0 0 1-1.5 0v-3a.75.75 0 0 1 1.5 0z" />
    </svg>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <circle cx="8" cy="8" r="6.25" />
      <path d="M8 4.5V8l2.4 1.4" />
    </svg>
  );
}

export function LocationPinIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden {...props}>
      <path d="M8 1.5a4.75 4.75 0 0 0-4.75 4.75c0 3.4 4.06 7.65 4.23 7.83a.75.75 0 0 0 1.04 0c.17-.18 4.23-4.43 4.23-7.83A4.75 4.75 0 0 0 8 1.5Zm0 6.6a1.85 1.85 0 1 1 0-3.7 1.85 1.85 0 0 1 0 3.7Z" />
    </svg>
  );
}

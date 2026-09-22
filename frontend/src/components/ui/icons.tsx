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

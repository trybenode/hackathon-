import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "fill" | "outline" | "ghost";
export type ButtonSize = "sm" | "md" | "lg" | "xl";

const variantClasses: Record<ButtonVariant, string> = {
  fill: "bg-primary-500 text-white hover:bg-primary-400",
  outline: "border border-navy-500 text-grey-900 hover:bg-grey-50",
  ghost: "text-grey-900 hover:bg-grey-50",
};

const sizeClasses: Record<ButtonSize, string> = {
  xl: "h-14 px-16 rounded-xl text-body-lg font-semibold",
  lg: "h-12 px-12 rounded-xl text-body-sm font-medium",
  md: "h-10 px-10 rounded-lg text-body-sm font-medium",
  sm: "h-8 px-6 rounded-pill text-body-sm font-medium",
};

export type ButtonProps = ComponentProps<"button"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
};

export function Button({
  variant = "fill",
  size = "md",
  fullWidth = false,
  type = "button",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 whitespace-nowrap transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        variantClasses[variant],
        sizeClasses[size],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    />
  );
}

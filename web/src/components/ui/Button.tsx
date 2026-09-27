import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "border border-transparent bg-accent text-white hover:bg-accent/90 active:bg-accent",
  secondary:
    "border border-border bg-surface text-text hover:bg-surface-2 active:bg-surface-2",
  ghost:
    "border border-transparent bg-transparent text-muted hover:bg-surface-2 hover:text-text active:bg-surface-2",
  danger:
    "border border-transparent bg-danger text-white hover:bg-danger/90 active:bg-danger",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 px-3 text-label",
  md: "h-9 gap-2 px-3.5 text-body",
  icon: "h-8 w-8 p-0",
};

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("h-3.5 w-3.5 animate-spin", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M21 12a9 9 0 0 0-9-9v3a6 6 0 0 1 6 6h3Z"
      />
    </svg>
  );
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    className,
    variant = "secondary",
    size = "md",
    loading = false,
    leftIcon,
    rightIcon,
    children,
    disabled,
    type = "button",
    ...props
  },
  ref,
) {
  const iconOnly = size === "icon";
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex select-none items-center justify-center whitespace-nowrap rounded-sm font-medium",
        "transition-colors duration-150 ease-out",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {loading ? <Spinner /> : leftIcon}
      {iconOnly ? null : children}
      {!loading && !iconOnly ? rightIcon : null}
    </button>
  );
});

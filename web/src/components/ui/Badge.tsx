import type { HTMLAttributes } from "react";

import { cn } from "../../lib/cn";

export type BadgeVariant =
  | "neutral"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "outline";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const VARIANTS: Record<BadgeVariant, string> = {
  neutral: "border-transparent bg-surface-2 text-muted",
  accent: "border-transparent bg-accent/15 text-accent",
  success: "border-transparent bg-success/15 text-success",
  warning: "border-transparent bg-warning/15 text-warning",
  danger: "border-transparent bg-danger/15 text-danger",
  outline: "border border-border text-muted",
};

export function Badge({ className, variant = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-label leading-none",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

export function StatusDot({ tone = "neutral", className }: { tone?: BadgeVariant; className?: string }) {
  const TONE: Record<string, string> = {
    neutral: "bg-muted",
    accent: "bg-accent",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    outline: "bg-muted",
  };
  return (
    <span
      className={cn("inline-block h-2 w-2 shrink-0 rounded-full", TONE[tone], className)}
      aria-hidden="true"
    />
  );
}

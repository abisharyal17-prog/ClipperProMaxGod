import { cn } from "../../lib/cn";

export type ProgressTone = "accent" | "success" | "warning" | "danger" | "neutral";

export interface ProgressProps {
  value: number;
  className?: string;
  tone?: ProgressTone;
  size?: "xs" | "sm" | "md";
  label?: string;
}

const TONES: Record<ProgressTone, string> = {
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-muted",
};

const SIZES: Record<NonNullable<ProgressProps["size"]>, string> = {
  xs: "h-0.5",
  sm: "h-1",
  md: "h-1.5",
};

export function Progress({ value, className, tone = "accent", size = "md", label }: ProgressProps) {
  const pct = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0)) * 100;
  return (
    <div
      className={cn("w-full overflow-hidden rounded-full bg-surface-2", SIZES[size], className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={label}
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-200 ease-out", TONES[tone])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

import { cn } from "../../lib/cn";

export interface SkeletonProps {
  className?: string;
}

/** A shaped placeholder. Always size it to match the content it reserves. */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "relative overflow-hidden rounded-sm bg-surface-2",
        "after:absolute after:inset-0 after:-translate-x-full after:bg-gradient-to-r after:from-transparent after:via-white/5 after:to-transparent motion-safe:after:animate-shimmer",
        className,
      )}
    />
  );
}

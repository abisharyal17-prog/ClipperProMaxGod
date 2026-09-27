import type { ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

import { cn } from "../../lib/cn";
import { Button, Skeleton } from "../ui";

/** A generic reserved-space loading block. Prefer shaped skeletons where you can. */
export function LoadingState({ label = "Loading", className }: { label?: string; className?: string }) {
  return (
    <div className={cn("space-y-3 py-6", className)} role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-6 w-1/3" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-danger/30 bg-danger/5 px-6 py-12 text-center",
        className,
      )}
    >
      <AlertCircle className="h-5 w-5 text-danger" aria-hidden="true" />
      <div className="space-y-1">
        <p className="text-body font-medium text-text">Request failed</p>
        <p className="max-w-md text-label text-muted">{message}</p>
      </div>
      {onRetry ? (
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
          onClick={onRetry}
        >
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-border px-6 py-14 text-center",
        className,
      )}
    >
      {icon ? <div className="text-muted">{icon}</div> : null}
      <div className="space-y-1">
        <p className="text-body font-medium text-text">{title}</p>
        {description ? (
          <p className="mx-auto max-w-md text-label text-muted">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_value, index) => (
        <Skeleton key={index} className={cn("h-4", index === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)}>
      <Skeleton className="h-9 w-full" />
      {Array.from({ length: rows }).map((_value, index) => (
        <Skeleton key={index} className="h-12 w-full" />
      ))}
    </div>
  );
}

export function SkeletonCardGrid({ count = 6, className }: { count?: number; className?: string }) {
  return (
    <div
      className={cn(
        "grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]",
        className,
      )}
    >
      {Array.from({ length: count }).map((_value, index) => (
        <div key={index} className="overflow-hidden rounded-lg border border-border bg-surface">
          <Skeleton className="aspect-video w-full rounded-none" />
          <div className="space-y-2 p-4">
            <Skeleton className="h-4 w-3/5" />
            <Skeleton className="h-3 w-2/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

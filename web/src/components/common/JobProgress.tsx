import { Loader2 } from "lucide-react";

import { cn } from "../../lib/cn";
import type { JobEvent, JobStage, JobStatus } from "../../lib/types";
import type { ConnectionState } from "../../hooks/useJobSocket";
import { Badge, Button, Progress } from "../ui";
import type { BadgeVariant } from "../ui";

export interface JobProgressProps {
  stage: JobStage | null;
  status: JobStatus | null;
  connection: ConnectionState;
  events: JobEvent[];
  overall: number;
  currentNodeLabel: string | null;
  error?: string | null;
  onCancel?: () => void;
  className?: string;
}

const STATUS_VARIANT: Record<JobStatus, BadgeVariant> = {
  queued: "warning",
  running: "accent",
  done: "success",
  error: "danger",
  cancelled: "neutral",
};

export function JobProgress({
  stage,
  status,
  connection,
  events,
  overall,
  currentNodeLabel,
  error,
  onCancel,
  className,
}: JobProgressProps) {
  const running =
    status === "running" || status === "queued" || connection === "open" || connection === "connecting";
  const lastMessage = [...events].reverse().find((event) => event.message)?.message ?? null;

  if (!stage && !status) return null;

  return (
    <div
      className={cn("w-full rounded-lg border border-border bg-surface px-4 py-3", className)}
    >
      <div className="flex items-center gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {running ? (
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-accent" aria-hidden="true" />
          ) : null}
          <span className="truncate text-label font-medium text-text">
            {stage ? `${stage === "analysis" ? "Analysis" : "Render"} job` : "Job"}
          </span>
          {status ? <Badge variant={STATUS_VARIANT[status]}>{status}</Badge> : null}
          {currentNodeLabel ? (
            <span className="truncate font-mono text-mono text-muted">{currentNodeLabel}</span>
          ) : null}
        </div>
        <span className="shrink-0 font-mono text-mono tabular-nums text-muted">
          {Math.round(overall * 100)}%
        </span>
        {running && onCancel ? (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
      <Progress value={overall} size="xs" className="mt-2.5" label="Job progress" />
      {error ? (
        <p className="mt-2 truncate text-label text-danger">{error}</p>
      ) : lastMessage ? (
        <p className="mt-1.5 truncate text-label text-muted">{lastMessage}</p>
      ) : null}
    </div>
  );
}

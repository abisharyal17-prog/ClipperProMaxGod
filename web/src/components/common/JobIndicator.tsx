import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { useActiveJob } from "../../context/ActiveJobContext";
import { isTerminal } from "../../hooks/useJobSocket";
import { Progress } from "../ui";

/** Global, shell-level job indicator: current node + real % from the WS. */
export function JobIndicator() {
  const { active, status, overall, currentNode, connection } = useActiveJob();

  const running =
    active != null && !isTerminal(status) && (connection !== "idle" || status != null);

  if (!running || !active) return null;

  const stageLabel = active.job.stage === "analysis" ? "Analysis" : "Render";
  const pct = Math.round(overall * 100);

  return (
    <Link
      to={`/p/${encodeURIComponent(active.projectId)}?tab=pipeline`}
      className="flex items-center gap-2.5 rounded-sm border border-border bg-surface-2 px-2.5 py-1.5 transition-colors duration-150 ease-out hover:border-muted/40"
      aria-label={`${stageLabel} job ${pct}% complete${currentNode ? `, ${currentNode}` : ""}`}
    >
      <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-accent" aria-hidden="true" />
      <span className="hidden min-w-0 flex-col sm:flex">
        <span className="truncate text-label text-text">{stageLabel}</span>
        {currentNode ? (
          <span className="truncate font-mono text-[10px] leading-tight text-muted">{currentNode}</span>
        ) : null}
      </span>
      <span className="hidden w-16 shrink-0 sm:block">
        <Progress value={overall} size="sm" label="Job progress" />
      </span>
      <span className="w-9 shrink-0 text-right font-mono text-label tabular-nums text-text">{pct}%</span>
    </Link>
  );
}

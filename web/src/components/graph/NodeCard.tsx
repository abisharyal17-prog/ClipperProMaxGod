import { Handle, Position } from "@xyflow/react";
import type { Node, NodeProps } from "@xyflow/react";

import { cn } from "../../lib/cn";
import { Progress } from "../ui";
import type { NodeRunStatus } from "../../hooks/useJobSocket";

export interface PipelineNodeData extends Record<string, unknown> {
  title: string;
  category: string;
  inputs: Record<string, string>;
  outputs: Record<string, string>;
  params: Record<string, unknown>;
  status: NodeRunStatus;
  pct: number;
}

export type PipelineNode = Node<PipelineNodeData, "pipeline">;

// Single-hue palette: accent at varying opacity, neutral for misc. Keeps the
// canvas on the one-accent rule instead of a rainbow of category colours.
const CATEGORY_COLORS: Record<string, string> = {
  input: "rgb(var(--accent) / 1)",
  audio: "rgb(var(--accent) / 0.85)",
  speech: "rgb(var(--accent) / 0.7)",
  video: "rgb(var(--accent) / 0.55)",
  clips: "rgb(var(--accent) / 0.9)",
  captions: "rgb(var(--accent) / 0.75)",
  output: "rgb(var(--accent) / 0.95)",
  misc: "rgb(var(--muted) / 0.8)",
};

export function categoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? CATEGORY_COLORS.misc;
}

const STATUS_BORDER: Record<NodeRunStatus, string> = {
  idle: "border-border",
  running: "border-accent",
  done: "border-success/70",
  cached: "border-muted/40",
  error: "border-danger",
};

const STATUS_LABEL: Record<NodeRunStatus, string> = {
  idle: "",
  running: "running",
  done: "done",
  cached: "cached",
  error: "error",
};

const handleStyle = (color: string) => ({
  position: "relative" as const,
  left: "auto",
  right: "auto",
  top: "auto",
  bottom: "auto",
  transform: "none",
  width: 8,
  height: 8,
  borderRadius: 9999,
  background: color,
});

export function NodeCard({ data, selected }: NodeProps<PipelineNode>) {
  const color = categoryColor(data.category);
  const inputs = Object.entries(data.inputs);
  const outputs = Object.entries(data.outputs);
  const status = data.status;
  const progress = status === "done" || status === "cached" ? 1 : data.pct;

  return (
    <div
      className={cn(
        "w-56 rounded-lg border bg-surface transition-colors duration-150 ease-out",
        STATUS_BORDER[status],
        selected && "ring-2 ring-accent ring-offset-2 ring-offset-bg",
      )}
    >
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <span
          className="h-2 w-2 shrink-0 rounded-full"
          style={{ backgroundColor: color }}
          aria-hidden="true"
        />
        <span className="truncate text-label font-semibold text-text" title={data.title}>
          {data.title}
        </span>
        {STATUS_LABEL[status] ? (
          <span
            className={cn(
              "ml-auto shrink-0 rounded-sm px-1.5 py-0.5 text-[10px] font-medium",
              status === "running" && "bg-accent/15 text-accent",
              status === "done" && "bg-success/15 text-success",
              status === "cached" && "bg-surface-2 text-muted",
              status === "error" && "bg-danger/15 text-danger",
            )}
          >
            {STATUS_LABEL[status]}
          </span>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-2 px-3 py-2">
        <div className="space-y-1">
          {inputs.map(([port, label]) => (
            <div key={port} className="flex items-center gap-1.5">
              <Handle type="target" id={port} position={Position.Left} style={handleStyle(color)} />
              <span className="truncate text-[10px] text-muted" title={label}>
                {label}
              </span>
            </div>
          ))}
        </div>
        <div className="space-y-1">
          {outputs.map(([port, label]) => (
            <div key={port} className="flex items-center justify-end gap-1.5">
              <span className="truncate text-right text-[10px] text-muted" title={label}>
                {label}
              </span>
              <Handle type="source" id={port} position={Position.Right} style={handleStyle(color)} />
            </div>
          ))}
        </div>
      </div>

      {status === "running" ? (
        <div className="px-3 pb-2">
          <Progress value={progress} size="xs" label={`${data.title} progress`} />
        </div>
      ) : null}
    </div>
  );
}

import { useMemo, useState } from "react";
import { Play, Waypoints } from "lucide-react";

import type { Graph, JobStage } from "../../lib/types";
import type { NodeRunState } from "../../hooks/useJobSocket";
import { ErrorState, LoadingState } from "../common/States";
import { PipelineGraph } from "../graph/PipelineGraph";
import { categoryColor } from "../graph/NodeCard";
import { Badge, Button, Card, Progress, Segmented } from "../ui";
import type { BadgeVariant } from "../ui";

export interface PipelineTabProps {
  stage: JobStage;
  onStageChange: (stage: JobStage) => void;
  graph: Graph | null;
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
  states: Record<string, NodeRunState>;
  running: boolean;
  onRun: (stage: JobStage) => void;
}

const STAGES = [
  { value: "analysis", label: "Analysis" },
  { value: "render", label: "Render" },
];

function statusVariant(status: NodeRunState["status"] | undefined): BadgeVariant {
  switch (status) {
    case "running":
      return "accent";
    case "done":
      return "success";
    case "cached":
      return "neutral";
    case "error":
      return "danger";
    default:
      return "outline";
  }
}

export function PipelineTab({
  stage,
  onStageChange,
  graph,
  isLoading,
  error,
  onRetry,
  states,
  running,
  onRun,
}: PipelineTabProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected = useMemo(
    () => graph?.nodes.find((node) => node.id === selectedId) ?? null,
    [graph, selectedId],
  );

  const categories = useMemo(() => {
    const set = new Set<string>();
    graph?.nodes.forEach((node) => set.add(node.data.category));
    return Array.from(set).sort();
  }, [graph]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented
          aria-label="Pipeline stage"
          options={STAGES}
          value={stage}
          onChange={(value) => onStageChange(value as JobStage)}
        />
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant={stage === "analysis" ? "primary" : "secondary"}
            size="sm"
            disabled={running}
            leftIcon={<Play className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => onRun("analysis")}
          >
            Run analysis
          </Button>
          <Button
            variant={stage === "render" ? "primary" : "secondary"}
            size="sm"
            disabled={running}
            leftIcon={<Play className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => onRun("render")}
          >
            Run render
          </Button>
        </div>
      </div>

      {categories.length > 0 ? (
        <div className="flex flex-wrap items-center gap-3">
          {categories.map((category) => (
            <span key={category} className="inline-flex items-center gap-1.5 text-label text-muted">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: categoryColor(category) }}
                aria-hidden="true"
              />
              {category}
            </span>
          ))}
        </div>
      ) : null}

      {isLoading ? (
        <LoadingState label="Loading pipeline graph" className="py-24" />
      ) : error ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Could not load the graph."}
          onRetry={onRetry}
        />
      ) : !graph || graph.nodes.length === 0 ? (
        <ErrorState message="This stage has no nodes yet." onRetry={onRetry} />
      ) : (
        <div className={selected ? "grid gap-4 lg:grid-cols-[1fr_320px]" : ""}>
          <Card className="h-[600px] overflow-hidden p-0">
            <PipelineGraph
              graph={graph}
              states={states}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </Card>

          {selected ? (
            <Card className="flex h-[600px] flex-col overflow-hidden">
              <div className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-body font-semibold text-text">{selected.data.title}</p>
                  <div className="mt-1 flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: categoryColor(selected.data.category) }}
                      aria-hidden="true"
                    />
                    <span className="text-label text-muted">{selected.data.category}</span>
                  </div>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setSelectedId(null)}>
                  Close
                </Button>
              </div>

              <div className="flex-1 space-y-4 overflow-y-auto scrollbar-thin px-4 py-3">
                <div className="space-y-1.5">
                  <p className="text-label font-medium text-muted">Status</p>
                  <div className="flex items-center gap-2">
                    <Badge variant={statusVariant(states[selected.id]?.status)}>
                      {states[selected.id]?.status ?? "idle"}
                    </Badge>
                    <span className="font-mono text-mono text-muted">{selected.id}</span>
                  </div>
                  {states[selected.id]?.status === "running" ? (
                    <Progress value={states[selected.id]?.pct ?? 0} size="xs" />
                  ) : null}
                </div>

                <div className="space-y-1.5">
                  <p className="text-label font-medium text-muted">Parameters</p>
                  {Object.keys(selected.data.params ?? {}).length === 0 ? (
                    <p className="text-label text-muted">No parameters.</p>
                  ) : (
                    <dl className="space-y-1">
                      {Object.entries(selected.data.params).map(([key, value]) => (
                        <div key={key} className="flex items-start justify-between gap-3">
                          <dt className="shrink-0 text-label text-muted">{key}</dt>
                          <dd className="min-w-0 break-words text-right font-mono text-mono text-text">
                            {value === null || value === undefined
                              ? "—"
                              : typeof value === "object"
                                ? JSON.stringify(value)
                                : String(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </div>

                <div className="space-y-1.5">
                  <p className="text-label font-medium text-muted">Ports</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="mb-1 text-label text-muted">Inputs</p>
                      {Object.entries(selected.data.inputs ?? {}).map(([port, label]) => (
                        <p key={port} className="truncate font-mono text-mono text-text">
                          {label} <span className="text-muted">({port})</span>
                        </p>
                      ))}
                      {Object.keys(selected.data.inputs ?? {}).length === 0 ? (
                        <p className="font-mono text-mono text-muted">none</p>
                      ) : null}
                    </div>
                    <div>
                      <p className="mb-1 text-label text-muted">Outputs</p>
                      {Object.entries(selected.data.outputs ?? {}).map(([port, label]) => (
                        <p key={port} className="truncate font-mono text-mono text-text">
                          {label} <span className="text-muted">({port})</span>
                        </p>
                      ))}
                      {Object.keys(selected.data.outputs ?? {}).length === 0 ? (
                        <p className="font-mono text-mono text-muted">none</p>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 border-t border-border px-4 py-3">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={running}
                  className="flex-1"
                  onClick={() => onRun("analysis")}
                >
                  Run analysis
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={running}
                  className="flex-1"
                  onClick={() => onRun("render")}
                >
                  Run render
                </Button>
              </div>
            </Card>
          ) : (
            <Card className="hidden h-[600px] items-center justify-center p-6 text-center lg:flex">
              <div className="space-y-2">
                <Waypoints className="mx-auto h-6 w-6 text-muted" aria-hidden="true" />
                <p className="text-label text-muted">Select a node to inspect its parameters.</p>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

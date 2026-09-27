import { useMemo } from "react";
import { Background, BackgroundVariant, Controls, MiniMap, ReactFlow } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { Graph } from "../../lib/types";
import type { NodeRunState } from "../../hooks/useJobSocket";
import { NodeCard, categoryColor } from "./NodeCard";
import type { PipelineNode, PipelineNodeData } from "./NodeCard";

const nodeTypes = { pipeline: NodeCard };

export interface PipelineGraphProps {
  graph: Graph;
  states: Record<string, NodeRunState>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export function PipelineGraph({ graph, states, selectedId, onSelect }: PipelineGraphProps) {
  const nodes = useMemo<PipelineNode[]>(
    () =>
      graph.nodes.map((node) => {
        const state = states[node.id];
        const data: PipelineNodeData = {
          title: node.data.title,
          category: node.data.category,
          inputs: node.data.inputs ?? {},
          outputs: node.data.outputs ?? {},
          params: node.data.params ?? {},
          status: state?.status ?? "idle",
          pct: state?.pct ?? 0,
        };
        return {
          id: node.id,
          type: "pipeline",
          position: node.position ?? { x: node.ui?.x ?? 0, y: node.ui?.y ?? 0 },
          data,
          selected: node.id === selectedId,
        };
      }),
    [graph, states, selectedId],
  );

  const edges = useMemo<Edge[]>(
    () =>
      graph.edges.map((edge) => {
        const status = states[edge.source]?.status;
        const stroke =
          status === "done" || status === "cached"
            ? "rgb(var(--success))"
            : status === "running"
              ? "rgb(var(--accent))"
              : "rgb(var(--border))";
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle ?? undefined,
          targetHandle: edge.targetHandle ?? undefined,
          animated: status === "running",
          type: "smoothstep",
          style: { stroke, strokeWidth: 1.5 },
        };
      }),
    [graph, states],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      minZoom={0.2}
      maxZoom={1.75}
      nodesConnectable={false}
      onNodeClick={(_event, node: Node) => onSelect(node.id)}
      onPaneClick={() => onSelect(null)}
      className="bg-bg"
    >
      <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="rgb(var(--border))" />
      <Controls showInteractive={false} />
      <MiniMap
        pannable
        zoomable
        nodeStrokeWidth={2}
        nodeColor={(node: Node) => {
          const category = (node.data as PipelineNodeData | undefined)?.category ?? "misc";
          return categoryColor(category);
        }}
        className="bg-surface"
      />
    </ReactFlow>
  );
}

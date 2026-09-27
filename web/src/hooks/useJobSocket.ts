import { useEffect, useState } from "react";

import { jobSocketUrl } from "../lib/api";
import type { JobEvent, JobStatus } from "../lib/types";

export type ConnectionState = "idle" | "connecting" | "open" | "closed";

export interface JobSocketState {
  events: JobEvent[];
  status: JobStatus | null;
  connection: ConnectionState;
  error: string | null;
}

const TERMINAL_STATUSES: ReadonlySet<string> = new Set(["done", "error", "cancelled"]);

export function isTerminal(status: JobStatus | null): boolean {
  return status != null && TERMINAL_STATUSES.has(status);
}

/**
 * Subscribes to `WS /ws/jobs/{id}`. The server replays the job's events on
 * connect, then streams new ones, ending with a `__status` terminal message.
 */
export function useJobSocket(jobId: string | null): JobSocketState {
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setEvents([]);
      setStatus(null);
      setConnection("idle");
      setError(null);
      return;
    }

    let socket: WebSocket | null = null;
    let disposed = false;

    setEvents([]);
    setStatus(null);
    setError(null);
    setConnection("connecting");

    try {
      socket = new WebSocket(jobSocketUrl(jobId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to open job socket");
      setConnection("closed");
      return;
    }

    socket.onopen = () => {
      if (!disposed) setConnection("open");
    };

    socket.onmessage = (message: MessageEvent<string>) => {
      if (disposed) return;
      let payload: unknown;
      try {
        payload = JSON.parse(message.data);
      } catch {
        return;
      }
      if (!payload || typeof payload !== "object") return;
      const record = payload as Record<string, unknown>;

      if (record.type === "__status") {
        const next = record.status;
        if (typeof next === "string") setStatus(next as JobStatus);
        setConnection("closed");
        return;
      }

      if (typeof record.type === "string") {
        setEvents((prev) => [...prev, record as unknown as JobEvent]);
      }
    };

    socket.onerror = () => {
      if (!disposed) setError("Job socket error");
    };

    socket.onclose = () => {
      if (!disposed) setConnection("closed");
    };

    return () => {
      disposed = true;
      socket?.close();
    };
  }, [jobId]);

  return { events, status, connection, error };
}

export type NodeRunStatus = "idle" | "running" | "done" | "cached" | "error";

export interface NodeRunState {
  status: NodeRunStatus;
  pct: number;
}

/** Collapse a job's event stream into per-node run state. */
export function deriveNodeStates(events: JobEvent[]): Record<string, NodeRunState> {
  const states: Record<string, NodeRunState> = {};
  for (const event of events) {
    if (!event.node) continue;
    const prev = states[event.node] ?? { status: "idle", pct: 0 };
    switch (event.type) {
      case "start":
        states[event.node] = { status: "running", pct: event.pct ?? 0 };
        break;
      case "progress":
        states[event.node] = { status: "running", pct: event.pct ?? prev.pct };
        break;
      case "done":
        states[event.node] = { status: event.cached ? "cached" : "done", pct: 1 };
        break;
      case "error":
        states[event.node] = { status: "error", pct: prev.pct };
        break;
      case "log":
        if (event.level === "error") states[event.node] = { status: "error", pct: prev.pct };
        break;
      default:
        states[event.node] = prev;
    }
  }
  return states;
}

/** Fraction (0..1) of a run complete, given the rendered node ids. */
export function overallProgress(
  states: Record<string, NodeRunState>,
  nodeIds: string[],
): number {
  if (nodeIds.length === 0) return 0;
  let progress = 0;
  for (const id of nodeIds) {
    const state = states[id];
    if (!state) continue;
    if (state.status === "done" || state.status === "cached") progress += 1;
    else if (state.status === "running") progress += state.pct;
  }
  return Math.max(0, Math.min(1, progress / nodeIds.length));
}

/** The node currently executing, if any. */
export function currentNodeId(events: JobEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event.node && (event.type === "start" || event.type === "progress")) {
      return event.node;
    }
  }
  return null;
}

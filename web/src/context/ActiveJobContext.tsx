import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { Job, JobEvent, JobStatus } from "../lib/types";
import {
  currentNodeId,
  deriveNodeStates,
  overallProgress,
  useJobSocket,
} from "../hooks/useJobSocket";
import type { ConnectionState, NodeRunState } from "../hooks/useJobSocket";

export interface ActiveJob {
  job: Job;
  projectId: string;
}

export interface ActiveJobContextValue {
  active: ActiveJob | null;
  events: JobEvent[];
  status: JobStatus | null;
  connection: ConnectionState;
  error: string | null;
  nodeStates: Record<string, NodeRunState>;
  overall: number;
  currentNode: string | null;
  setActiveJob: (job: Job, projectId: string) => void;
  clearActiveJob: () => void;
}

const ActiveJobContext = createContext<ActiveJobContextValue | null>(null);

export function ActiveJobProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ActiveJob | null>(null);

  const socket = useJobSocket(active?.job.id ?? null);
  const nodeStates = useMemo(() => deriveNodeStates(socket.events), [socket.events]);
  const overall = useMemo(
    () => overallProgress(nodeStates, Object.keys(nodeStates)),
    [nodeStates],
  );
  const currentNode = useMemo(() => currentNodeId(socket.events), [socket.events]);

  const setActiveJob = useCallback((job: Job, projectId: string) => {
    setActive((current) => {
      if (current?.job.id === job.id && current.projectId === projectId) return current;
      return { job, projectId };
    });
  }, []);

  const clearActiveJob = useCallback(() => setActive(null), []);

  const value = useMemo<ActiveJobContextValue>(
    () => ({
      active,
      events: socket.events,
      status: socket.status,
      connection: socket.connection,
      error: socket.error,
      nodeStates,
      overall,
      currentNode,
      setActiveJob,
      clearActiveJob,
    }),
    [
      active,
      socket.events,
      socket.status,
      socket.connection,
      socket.error,
      nodeStates,
      overall,
      currentNode,
      setActiveJob,
      clearActiveJob,
    ],
  );

  return <ActiveJobContext.Provider value={value}>{children}</ActiveJobContext.Provider>;
}

export function useActiveJob(): ActiveJobContextValue {
  const context = useContext(ActiveJobContext);
  if (!context) {
    throw new Error("useActiveJob must be used within an ActiveJobProvider");
  }
  return context;
}

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Captions,
  Film,
  ListVideo,
  Play,
  SlidersHorizontal,
  Waypoints,
} from "lucide-react";

import { ApiError, api, queryKeys } from "../lib/api";
import { errorMessage } from "../lib/errors";
import type { AnalysisOptions, JobStage, RenderOptions } from "../lib/types";
import { isTerminal, overallProgress } from "../hooks/useJobSocket";
import { useActiveJob } from "../context/ActiveJobContext";
import { ErrorState, LoadingState } from "../components/common/States";
import { JobProgress } from "../components/common/JobProgress";
import { PipelineTab } from "../components/workspace/PipelineTab";
import { TranscriptTab } from "../components/workspace/TranscriptTab";
import { ClipsTab } from "../components/workspace/ClipsTab";
import { EditorTab } from "../components/workspace/EditorTab";
import { RendersTab } from "../components/workspace/RendersTab";
import { Badge, Button, Dialog, Tabs, useToast } from "../components/ui";
import type { TabItem } from "../components/ui";

type WorkspaceTab = "pipeline" | "transcript" | "clips" | "editor" | "renders";

const TAB_VALUES: WorkspaceTab[] = ["pipeline", "transcript", "clips", "editor", "renders"];

export default function Workspace() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    active,
    setActiveJob,
    nodeStates,
    status: socketStatus,
    connection: socketConnection,
    events: socketEvents,
    error: socketError,
    currentNode,
  } = useActiveJob();

  const rawTab = searchParams.get("tab");
  const tab: WorkspaceTab = TAB_VALUES.includes(rawTab as WorkspaceTab)
    ? (rawTab as WorkspaceTab)
    : "pipeline";
  const setTab = (value: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", value);
    setSearchParams(next, { replace: true });
  };

  const [pipelineStage, setPipelineStage] = useState<JobStage>("analysis");
  const [cookiesGate, setCookiesGate] = useState(false);

  const projectQuery = useQuery({
    queryKey: queryKeys.project(id),
    queryFn: () => api.project(id),
    enabled: Boolean(id),
  });

  const settingsQuery = useQuery({ queryKey: queryKeys.settings, queryFn: api.getSettings });
  const stylesQuery = useQuery({ queryKey: queryKeys.styles, queryFn: api.styles });
  const assetsQuery = useQuery({ queryKey: queryKeys.assets, queryFn: api.assets });

  const analysisGraphQuery = useQuery({
    queryKey: queryKeys.graph(id, "analysis"),
    queryFn: () => api.graph(id, "analysis"),
    enabled: Boolean(id),
  });
  const renderGraphQuery = useQuery({
    queryKey: queryKeys.graph(id, "render"),
    queryFn: () => api.graph(id, "render"),
    enabled: Boolean(id),
  });

  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs(id),
    queryFn: () => api.jobs(id),
    enabled: Boolean(id),
  });

  // Adopt a job that is still running when the workspace is opened/reloaded.
  const adopted = useRef(false);
  useEffect(() => {
    if (adopted.current || !jobsQuery.data) return;
    adopted.current = true;
    const running = jobsQuery.data.find(
      (job) => job.status === "running" || job.status === "queued",
    );
    if (running) {
      setActiveJob(running, id);
      setPipelineStage(running.stage);
    }
  }, [jobsQuery.data, id, setActiveJob]);

  const createJobMutation = useMutation({
    mutationFn: (variables: { stage: JobStage; options?: RenderOptions | AnalysisOptions }) =>
      api.createJob(id, { stage: variables.stage, options: variables.options }),
    onSuccess: (job) => {
      setActiveJob(job, id);
      setPipelineStage(job.stage);
      toast.info(`${job.stage === "analysis" ? "Analysis" : "Render"} job started`);
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs(id) });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        const body = (error.detail ?? {}) as Record<string, unknown>;
        const inner = (body.detail ?? body) as Record<string, unknown>;
        if (inner && inner.code === "cookies_required") {
          setCookiesGate(true);
          return;
        }
      }
      toast.error("Could not start job", { description: errorMessage(error) });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => api.cancelJob(jobId),
    onSuccess: () => toast.info("Job cancelled"),
    onError: (error) => toast.error("Could not cancel job", { description: errorMessage(error) }),
  });

  const activeForProject = active && active.projectId === id ? active : null;
  const status = activeForProject ? socketStatus : null;
  const running = activeForProject != null && !isTerminal(status);

  // Refresh derived data once a job reaches a terminal state.
  const handledStatus = useRef<string | null>(null);
  useEffect(() => {
    if (!activeForProject || !status || !isTerminal(status)) return;
    const key = `${activeForProject.job.id}:${status}`;
    if (handledStatus.current === key) return;
    handledStatus.current = key;
    void queryClient.invalidateQueries({ queryKey: queryKeys.project(id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.text(id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.metadata(id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.jobs(id) });
    if (status === "done") {
      toast.success(
        `${activeForProject.job.stage === "analysis" ? "Analysis" : "Render"} finished`,
      );
    } else if (status === "error") {
      toast.error(`${activeForProject.job.stage} failed`, {
        description: activeForProject.job.error ?? undefined,
      });
    }
  }, [activeForProject, status, id, queryClient, toast]);

  const graphForStage = (stage: JobStage) =>
    stage === "analysis" ? analysisGraphQuery.data : renderGraphQuery.data;

  const nodeIds = useMemo(
    () => graphForStage(pipelineStage)?.nodes.map((node) => node.id) ?? [],
    [pipelineStage, analysisGraphQuery.data, renderGraphQuery.data],
  );
  const overall = useMemo(
    () => overallProgress(activeForProject ? nodeStates : {}, nodeIds),
    [activeForProject, nodeStates, nodeIds],
  );

  const currentNodeLabel =
    activeForProject && currentNode
      ? graphForStage(activeForProject.job.stage)?.nodes.find((node) => node.id === currentNode)?.data
          .title ?? currentNode
      : null;

  const runJob = (stage: JobStage, options?: RenderOptions | AnalysisOptions) => {
    if (running || createJobMutation.isPending) return; // guard every entry point
    const defaults: RenderOptions | AnalysisOptions =
      stage === "analysis"
        ? { n_clips: 8, min_duration: 15, max_duration: 60 }
        : { reframe: "auto", platform: "shorts", add_titles: true, track: true };
    createJobMutation.mutate({ stage, options: options ?? defaults });
  };

  if (projectQuery.isLoading) {
    return <LoadingState label="Loading project" />;
  }
  if (projectQuery.isError || !projectQuery.data) {
    return (
      <ErrorState
        message={projectQuery.isError ? errorMessage(projectQuery.error) : "Project not found."}
        onRetry={() => void projectQuery.refetch()}
      />
    );
  }

  const detail = projectQuery.data;
  const summary = detail.summary;

  const tabs: TabItem[] = [
    { value: "pipeline", label: "Pipeline", icon: <Waypoints className="h-3.5 w-3.5" aria-hidden="true" /> },
    { value: "transcript", label: "Transcript", icon: <Captions className="h-3.5 w-3.5" aria-hidden="true" /> },
    {
      value: "clips",
      label: "Clips",
      icon: <ListVideo className="h-3.5 w-3.5" aria-hidden="true" />,
      badge:
        summary.clip_count > 0 ? (
          <Badge variant="neutral" className="px-1.5 py-0">
            {summary.clip_count}
          </Badge>
        ) : undefined,
    },
    { value: "editor", label: "Editor", icon: <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" /> },
    {
      value: "renders",
      label: "Renders",
      icon: <Film className="h-3.5 w-3.5" aria-hidden="true" />,
      badge:
        summary.render_count > 0 ? (
          <Badge variant="neutral" className="px-1.5 py-0">
            {summary.render_count}
          </Badge>
        ) : undefined,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-label font-medium text-muted transition-colors duration-150 ease-out hover:text-text"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          All projects
        </Link>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-title text-text">{summary.title?.trim() || summary.id}</h1>
            <p className="mt-1 truncate text-body text-muted" title={summary.source ?? undefined}>
              {summary.source ?? "No source"}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Badge variant={summary.has_source ? "success" : "outline"}>
                {summary.has_source ? "Source" : "No source"}
              </Badge>
              <Badge variant={summary.has_transcript ? "success" : "outline"}>
                {summary.has_transcript ? "Transcript" : "No transcript"}
              </Badge>
              <Badge variant={summary.has_clips ? "success" : "outline"}>
                {summary.has_clips ? "Clips" : "No clips"}
              </Badge>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={running || createJobMutation.isPending}
              leftIcon={<Play className="h-3.5 w-3.5" aria-hidden="true" />}
              onClick={() => runJob("analysis")}
            >
              Run analysis
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={running || createJobMutation.isPending}
              leftIcon={<Play className="h-3.5 w-3.5" aria-hidden="true" />}
              onClick={() => runJob("render")}
            >
              Run render
            </Button>
          </div>
        </div>

        {activeForProject ? (
          <JobProgress
            stage={activeForProject.job.stage}
            status={status ?? activeForProject.job.status}
            connection={activeForProject ? socketConnection : "idle"}
            events={activeForProject && socketEvents.length > 0 ? socketEvents : activeForProject.job.events}
            overall={overall}
            currentNodeLabel={currentNodeLabel}
            error={activeForProject ? socketError ?? activeForProject.job.error : null}
            onCancel={
              running ? () => cancelMutation.mutate(activeForProject.job.id) : undefined
            }
          />
        ) : null}
      </div>

      <Tabs items={tabs} value={tab} onChange={setTab} />

      <div
        id={`tab-${tab}-panel`}
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        tabIndex={-1}
        className="focus-visible:outline-none"
      >
      {tab === "pipeline" ? (
        <PipelineTab
          stage={pipelineStage}
          onStageChange={setPipelineStage}
          graph={graphForStage(pipelineStage) ?? null}
          isLoading={
            pipelineStage === "analysis" ? analysisGraphQuery.isLoading : renderGraphQuery.isLoading
          }
          error={pipelineStage === "analysis" ? analysisGraphQuery.error : renderGraphQuery.error}
          onRetry={() =>
            void (pipelineStage === "analysis" ? analysisGraphQuery.refetch() : renderGraphQuery.refetch())
          }
          states={nodeStates}
          running={running || createJobMutation.isPending}
          onRun={(stage) => runJob(stage)}
        />
      ) : tab === "transcript" ? (
        <TranscriptTab
          projectId={id}
          onRunAnalysis={() => runJob("analysis")}
          runDisabled={running || createJobMutation.isPending}
        />
      ) : (
        // Clips and Editor stay mounted so in-progress edits survive tab switches.
        <>
          <div className={tab === "clips" ? undefined : "hidden"}>
            <ClipsTab projectId={id} clips={detail.clips} />
          </div>
          <div className={tab === "editor" ? undefined : "hidden"}>
            <EditorTab
              projectId={id}
              clips={detail.clips}
              styles={stylesQuery.data ?? []}
              assets={assetsQuery.data ?? null}
              defaultCaptionStyle={settingsQuery.data?.default_caption_style ?? null}
              defaultReframe={settingsQuery.data?.default_reframe ?? "auto"}
              optionsLoading={
                stylesQuery.isLoading || assetsQuery.isLoading || settingsQuery.isLoading
              }
              renderPending={running && activeForProject?.job.stage === "render"}
              submitPending={createJobMutation.isPending}
              onRenderSelected={(options) => runJob("render", options)}
            />
          </div>
          {tab === "renders" ? <RendersTab projectId={id} renders={detail.renders} /> : null}
        </>
      )}
      </div>

      <Dialog
        open={cookiesGate}
        onClose={() => setCookiesGate(false)}
        title="Cookies required"
        description="This URL needs a signed-in YouTube session before Clipper can download it."
        footer={
          <>
            <Button variant="secondary" onClick={() => setCookiesGate(false)}>
              Not now
            </Button>
            <Button
              onClick={() => {
                setCookiesGate(false);
                navigate("/settings");
              }}
            >
              Open Settings
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">
          Add your YouTube cookies under <span className="text-text">Settings → Cookies</span> (paste
          a JSON export or a cookies.txt, then Verify). Cookies are stored once and shared by every
          project.
        </p>
      </Dialog>
    </div>
  );
}

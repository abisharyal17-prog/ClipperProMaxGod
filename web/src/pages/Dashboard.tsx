import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Film, Plus, Search, Trash2, Upload } from "lucide-react";

import { api, exportProjectUrl, importProject, mediaUrl, queryKeys } from "../lib/api";
import { errorMessage } from "../lib/errors";
import { relativeTime, titleOf } from "../lib/format";
import type { ProjectSummary } from "../lib/types";
import { NewProjectDialog } from "../components/NewProjectDialog";
import { EmptyState, ErrorState, SkeletonCardGrid } from "../components/common/States";
import { Badge, Button, Card, Dialog, Input, Menu, useToast } from "../components/ui";

function downloadExport(projectId: string): void {
  const link = document.createElement("a");
  link.href = exportProjectUrl(projectId);
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
}


function ProjectCard({
  project,
  onRequestDelete,
}: {
  project: ProjectSummary;
  onRequestDelete: (project: ProjectSummary) => void;
}) {
  const title = titleOf(project);
  const thumbnail = mediaUrl(project.thumbnail);
  const href = `/p/${encodeURIComponent(project.id)}`;

  return (
    <Card interactive className="group flex flex-col overflow-hidden">
      <div className="relative">
        <Link to={href} className="block" aria-label={`Open ${title}`}>
          <div className="relative aspect-video w-full overflow-hidden border-b border-border bg-surface-2">
            {thumbnail ? (
              <img
                src={thumbnail}
                alt=""
                loading="lazy"
                className="h-full w-full object-cover"
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                }}
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted">
                <Film className="h-8 w-8" aria-hidden="true" />
              </div>
            )}
          </div>
        </Link>
        <div className="absolute right-2 top-2 opacity-0 transition-opacity duration-150 ease-out group-hover:opacity-100 group-focus-within:opacity-100 [@media(pointer:coarse)]:opacity-100">
          <span className="rounded-sm bg-surface/95 shadow-overlay">
            <Menu
              ariaLabel={`Actions for ${title}`}
              align="right"
              items={[
                {
                  label: "Export",
                  icon: <Download className="h-3.5 w-3.5" aria-hidden="true" />,
                  onSelect: () => downloadExport(project.id),
                },
                {
                  label: "Delete",
                  icon: <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />,
                  danger: true,
                  onSelect: () => onRequestDelete(project),
                },
              ]}
            />
          </span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="min-w-0">
          <Link
            to={href}
            className="block truncate text-body font-semibold text-text transition-colors duration-150 ease-out hover:text-accent"
            title={title}
          >
            {title}
          </Link>
          <p
            className="mt-0.5 truncate text-label text-muted"
            title={project.source ?? undefined}
          >
            {project.source ?? "No source"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="neutral">{project.clip_count} clips</Badge>
          <Badge variant="neutral">{project.render_count} renders</Badge>
          {project.has_transcript ? <Badge variant="success">transcript</Badge> : null}
        </div>

        <div className="mt-auto flex items-center justify-between border-t border-border pt-3">
          <span className="text-label text-muted">Modified {relativeTime(project.modified)}</span>
        </div>
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<ProjectSummary | null>(null);

  const projectsQuery = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.projects,
  });

  const deleteMutation = useMutation({
    mutationFn: (project: ProjectSummary) => api.deleteProject(project.id),
    onSuccess: (_result, project) => {
      toast.success("Project deleted", { description: titleOf(project) });
      setPendingDelete(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    },
    onError: (error) => toast.error("Could not delete project", { description: errorMessage(error) }),
  });

  const fileInputRef = useRef<HTMLInputElement>(null);

  const importMutation = useMutation({
    mutationFn: (file: File) => importProject(file),
    onSuccess: (project) => {
      toast.success("Project imported", { description: titleOf(project) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects });
      navigate(`/p/${encodeURIComponent(project.id)}`);
    },
    onError: (error) => toast.error("Could not import project", { description: errorMessage(error) }),
  });

  const projects = projectsQuery.data ?? [];

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return projects;
    return projects.filter((project) => {
      const haystack = `${project.title ?? ""} ${project.id} ${project.source ?? ""}`.toLowerCase();
      return haystack.includes(term);
    });
  }, [projects, search]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-display text-text">Projects</h1>
        <p className="mt-1 text-body text-muted">
          Convert long-form videos into short, captioned clips.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[16rem] flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <Input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search projects"
            className="pl-9"
            aria-label="Search projects"
          />
        </div>
        <Button
          variant="secondary"
          leftIcon={<Upload className="h-4 w-4" aria-hidden="true" />}
          loading={importMutation.isPending}
          onClick={() => fileInputRef.current?.click()}
        >
          Import
        </Button>
        <Button
          variant="primary"
          leftIcon={<Plus className="h-4 w-4" aria-hidden="true" />}
          onClick={() => setDialogOpen(true)}
        >
          New project
        </Button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".zip,application/zip"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) importMutation.mutate(file);
        }}
      />

      {projectsQuery.isLoading ? (
        <SkeletonCardGrid count={8} />
      ) : projectsQuery.isError ? (
        <ErrorState
          message={errorMessage(projectsQuery.error)}
          onRetry={() => void projectsQuery.refetch()}
        />
      ) : projects.length === 0 ? (
        <EmptyState
          icon={<Film className="h-6 w-6" aria-hidden="true" />}
          title="No projects yet"
          description="Create a project from a video URL or a local file to start transcribing and clipping."
          action={
            <Button
              variant="primary"
              leftIcon={<Plus className="h-4 w-4" aria-hidden="true" />}
              onClick={() => setDialogOpen(true)}
            >
              New project
            </Button>
          }
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No matching projects"
          description={`Nothing matches “${search}”. Try a different search.`}
          action={
            <Button variant="secondary" onClick={() => setSearch("")}>
              Clear search
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]">
          {filtered.map((project) => (
            <ProjectCard key={project.id} project={project} onRequestDelete={setPendingDelete} />
          ))}
        </div>
      )}

      <NewProjectDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={(project) => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.projects });
          setDialogOpen(false);
          navigate(`/p/${encodeURIComponent(project.id)}`);
        }}
      />

      <Dialog
        open={pendingDelete != null}
        onClose={() => setPendingDelete(null)}
        title="Delete project"
        description={
          pendingDelete
            ? `Delete “${titleOf(pendingDelete)}”? This removes its transcript, clips and renders.`
            : undefined
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={deleteMutation.isPending}
              onClick={() => pendingDelete && deleteMutation.mutate(pendingDelete)}
            >
              Delete
            </Button>
          </>
        }
      />
    </div>
  );
}

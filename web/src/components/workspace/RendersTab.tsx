import { useQuery } from "@tanstack/react-query";
import { Download, Film, Hash, Tag } from "lucide-react";

import { api, mediaUrl, queryKeys } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { formatDuration } from "../../lib/format";
import type { MetadataPack, Render } from "../../lib/types";
import { CopyButton } from "../common/CopyButton";
import { EmptyState, ErrorState, LoadingState } from "../common/States";
import { Badge, Card, CardBody, CardHeader, CardTitle } from "../ui";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

interface PublishPack {
  title: string | null;
  hashtags: string[];
  filename: string | null;
}

function toStringOrNull(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return String(value);
  return null;
}

function toHashtags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
  if (typeof value === "string") {
    return value
      .split(/[\s,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function findPack(metadata: MetadataPack | undefined, clipId: string): PublishPack | null {
  if (!metadata || !isRecord(metadata.metadata)) return null;
  const candidates: Record<string, unknown>[] = [];
  const collect = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (isRecord(item)) candidates.push(item);
      });
    } else if (isRecord(value)) {
      candidates.push(value);
      Object.values(value).forEach((inner) => {
        if (Array.isArray(inner)) {
          inner.forEach((item) => {
            if (isRecord(item)) candidates.push(item);
          });
        }
      });
    }
  };
  Object.values(metadata.metadata).forEach(collect);

  const found = candidates.find((item) => item.clip_id === clipId || item.id === clipId);
  if (!found) return null;
  return {
    title: toStringOrNull(found.title) ?? toStringOrNull(found.name),
    hashtags: toHashtags(found.hashtags ?? found.tags ?? found.keywords),
    filename: toStringOrNull(found.filename) ?? toStringOrNull(found.file),
  };
}

function packText(pack: PublishPack): string {
  return [pack.title ?? "", pack.hashtags.join(" "), pack.filename ?? ""]
    .filter((line) => line.trim())
    .join("\n");
}

function RenderCard({ render, pack }: { render: Render; pack: PublishPack | null }) {
  const src = mediaUrl(render.url);
  return (
    <Card className="flex flex-col overflow-hidden">
      <div className="border-b border-border bg-black">
        <video
          src={src}
          controls
          preload="metadata"
          className="aspect-[9/16] max-h-96 w-full object-contain"
        />
      </div>
      <CardBody className="flex flex-1 flex-col gap-3">
        <div className="min-w-0">
          <p className="truncate text-body font-semibold text-text">
            {render.title?.trim() || render.clip_id}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge variant="neutral">{formatDuration(render.duration)}</Badge>
            <Badge variant="outline">{render.camera}</Badge>
            <Badge variant="outline">{render.reframe}</Badge>
          </div>
        </div>

        {pack ? (
          <div className="space-y-1.5 rounded-md border border-border bg-surface-2 p-2.5">
            {pack.title ? (
              <p className="flex items-start gap-1.5 text-label text-text">
                <Tag className="mt-0.5 h-3 w-3 shrink-0 text-muted" aria-hidden="true" />
                <span className="line-clamp-2">{pack.title}</span>
              </p>
            ) : null}
            {pack.hashtags.length > 0 ? (
              <p className="flex items-start gap-1.5 text-label text-text">
                <Hash className="mt-0.5 h-3 w-3 shrink-0 text-muted" aria-hidden="true" />
                <span className="line-clamp-2 break-all">{pack.hashtags.join(" ")}</span>
              </p>
            ) : null}
            {pack.filename ? (
              <p className="truncate font-mono text-mono text-muted">{pack.filename}</p>
            ) : null}
          </div>
        ) : null}

        <div className="mt-auto flex items-center justify-between gap-2">
          <Badge variant="accent">{render.clip_id}</Badge>
          <div className="flex items-center gap-2">
            {pack ? <CopyButton text={packText(pack)} label="Copy pack" size="sm" /> : null}
            <a
              href={src}
              download
              className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-label font-medium text-text transition-colors duration-150 ease-out hover:bg-surface-2"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              Download
            </a>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

export function RendersTab({ projectId, renders }: { projectId: string; renders: Render[] }) {
  const metadataQuery = useQuery({
    queryKey: queryKeys.metadata(projectId),
    queryFn: () => api.metadata(projectId),
    enabled: Boolean(projectId) && renders.length > 0,
  });

  if (renders.length === 0) {
    return (
      <EmptyState
        icon={<Film className="h-6 w-6" aria-hidden="true" />}
        title="No renders yet"
        description="Configure clips in the Editor tab and run a render to produce finished vertical videos."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
        {renders.map((render) => (
          <RenderCard
            key={`${render.clip_id}-${render.path}`}
            render={render}
            pack={findPack(metadataQuery.data, render.clip_id)}
          />
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Publish pack</CardTitle>
          <div className="flex items-center gap-2">
            {metadataQuery.isLoading ? <span className="text-label text-muted">Loading…</span> : null}
            <CopyButton
              text={metadataQuery.data?.markdown ?? ""}
              disabled={!metadataQuery.data?.markdown}
              label="Copy all"
            />
          </div>
        </CardHeader>
        <CardBody className="p-0">
          {metadataQuery.isError ? (
            <ErrorState
              message={errorMessage(metadataQuery.error)}
              onRetry={() => void metadataQuery.refetch()}
              className="m-4"
            />
          ) : metadataQuery.isLoading ? (
            <LoadingState label="Loading metadata" className="px-4" />
          ) : metadataQuery.data?.markdown ? (
            <pre className="max-h-80 overflow-auto scrollbar-thin whitespace-pre-wrap break-words px-4 py-3 font-mono text-mono text-text">
              {metadataQuery.data.markdown}
            </pre>
          ) : (
            <p className="px-4 py-8 text-center text-label text-muted">
              No publish metadata available.
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

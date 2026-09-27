import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDownWideNarrow, ArrowUpNarrowWide, Save, Scissors } from "lucide-react";

import { api, queryKeys } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { formatClock, formatDuration } from "../../lib/format";
import type { Clip, ClipList } from "../../lib/types";
import { EmptyState } from "../common/States";
import {
  Badge,
  Button,
  Input,
  Progress,
  Switch,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
  useToast,
} from "../ui";

export interface ClipsTabProps {
  projectId: string;
  clips: ClipList | null;
}

function scoreValue(clip: Clip): number | null {
  return typeof clip.score === "number" && Number.isFinite(clip.score) ? clip.score : null;
}

export function ClipsTab({ projectId, clips }: ClipsTabProps) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Clip[]>([]);
  const [dirty, setDirty] = useState(false);
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    setDraft(clips ? clips.clips.map((clip) => ({ ...clip })) : []);
    setDirty(false);
  }, [clips]);

  const maxScore = useMemo(
    () => draft.reduce((max, clip) => Math.max(max, scoreValue(clip) ?? 0), 0) || 1,
    [draft],
  );

  const ordered = useMemo(() => {
    const copy = [...draft];
    copy.sort((a, b) => {
      const av = scoreValue(a);
      const bv = scoreValue(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return sortDesc ? bv - av : av - bv;
    });
    return copy;
  }, [draft, sortDesc]);

  const updateClip = (id: string, patch: Partial<Clip>) => {
    setDraft((current) => current.map((clip) => (clip.id === id ? { ...clip, ...patch } : clip)));
    setDirty(true);
  };

  const setAllEnabled = (enabled: boolean) => {
    setDraft((current) => current.map((clip) => ({ ...clip, enabled })));
    setDirty(true);
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!clips) throw new Error("No clips to save");
      const payload: ClipList = {
        version: clips.version,
        source: clips.source,
        defaults: clips.defaults,
        clips: draft,
      };
      return api.putClips(projectId, payload);
    },
    onSuccess: (saved) => {
      setDraft(saved.clips.map((clip) => ({ ...clip })));
      setDirty(false);
      toast.success("Clips saved");
      queryClient.setQueryData(queryKeys.project(projectId), (previous: unknown) =>
        previous && typeof previous === "object"
          ? { ...(previous as Record<string, unknown>), clips: saved }
          : previous,
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) });
    },
    onError: (error) => toast.error("Could not save clips", { description: errorMessage(error) }),
  });

  if (!clips || draft.length === 0) {
    return (
      <EmptyState
        icon={<Scissors className="h-6 w-6" aria-hidden="true" />}
        title="No clips yet"
        description="Run analysis to generate clip candidates, or import clips from the Transcript tab."
      />
    );
  }

  const enabledCount = draft.filter((clip) => clip.enabled).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-label text-muted">
          <span className="font-mono tabular-nums text-text">{draft.length}</span> clips
          <span aria-hidden="true">·</span>
          <span className="font-mono tabular-nums text-text">{enabledCount}</span> enabled
          {dirty ? <Badge variant="warning">unsaved</Badge> : null}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setAllEnabled(true)}>
            Enable all
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setAllEnabled(false)}>
            Disable all
          </Button>
          <Button
            variant="secondary"
            size="sm"
            leftIcon={
              sortDesc ? (
                <ArrowDownWideNarrow className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <ArrowUpNarrowWide className="h-3.5 w-3.5" aria-hidden="true" />
              )
            }
            onClick={() => setSortDesc((value) => !value)}
            aria-pressed={sortDesc}
          >
            {sortDesc ? "Highest score first" : "Lowest score first"}
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={!dirty}
            loading={saveMutation.isPending}
            leftIcon={<Save className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => saveMutation.mutate()}
          >
            Save
          </Button>
        </div>
      </div>

      <div className="max-h-[65vh] overflow-auto scrollbar-thin rounded-lg border border-border bg-surface">
        <Table>
          <THead>
            <TR className="hover:bg-transparent">
              <TH className="w-16">Include</TH>
              <TH className="w-40">Score</TH>
              <TH>Title</TH>
              <TH className="w-32">Start–end</TH>
              <TH className="w-20">Duration</TH>
              <TH className="hidden lg:table-cell">Hook</TH>
            </TR>
          </THead>
          <TBody>
            {ordered.map((clip) => {
              const score = scoreValue(clip);
              const ratio = score == null ? 0 : score / maxScore;
              const tone = score == null ? "neutral" : ratio >= 0.66 ? "success" : ratio >= 0.33 ? "accent" : "warning";
              return (
                <TR key={clip.id}>
                  <TD>
                    <Switch
                      checked={clip.enabled}
                      onChange={(checked) => updateClip(clip.id, { enabled: checked })}
                      label={`Toggle clip ${clip.id}`}
                    />
                  </TD>
                  <TD>
                    <div className="flex items-center gap-2">
                      <Progress
                        value={ratio}
                        tone={tone}
                        size="sm"
                        className="w-20"
                        label={`Score for ${clip.title?.trim() || clip.id}`}
                      />
                      <span className="w-10 text-right font-mono text-mono tabular-nums text-muted">
                        {score == null ? "—" : score.toFixed(1)}
                      </span>
                    </div>
                  </TD>
                  <TD>
                    <Input
                      value={clip.title ?? ""}
                      placeholder="Untitled"
                      aria-label={`Title for clip ${clip.id}`}
                      onChange={(event) => updateClip(clip.id, { title: event.target.value })}
                      className="h-8 min-w-[12rem]"
                    />
                  </TD>
                  <TD className="whitespace-nowrap font-mono text-mono tabular-nums">
                    {formatClock(clip.start)}–{formatClock(clip.end)}
                  </TD>
                  <TD className="font-mono text-mono tabular-nums text-muted">
                    {formatDuration(clip.end - clip.start)}
                  </TD>
                  <TD className="hidden max-w-xs lg:table-cell">
                    <span className="line-clamp-2 text-label text-muted">{clip.hook ?? "—"}</span>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </div>
    </div>
  );
}

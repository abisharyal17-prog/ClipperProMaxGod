import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, SlidersHorizontal, Trash2, Video } from "lucide-react";

import { api, queryKeys } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { formatClock, formatDuration } from "../../lib/format";
import type { Assets, CaptionStyle, Clip, ClipList, RenderOptions } from "../../lib/types";
import { cn } from "../../lib/cn";
import { EmptyState } from "../common/States";
import { Badge, Button, Card, Field, Input, Select, Switch, Textarea, useToast } from "../ui";

export interface EditorTabProps {
  projectId: string;
  clips: ClipList | null;
  styles: CaptionStyle[];
  assets: Assets | null;
  defaultCaptionStyle: string | null;
  defaultReframe: string;
  onRenderSelected: (options: RenderOptions) => void;
  renderPending: boolean;
}

const REFRAME_OPTIONS = [
  { value: "", label: "Default" },
  { value: "auto", label: "Auto" },
  { value: "crop", label: "Crop" },
  { value: "blur", label: "Blur" },
  { value: "pad", label: "Pad" },
];

export function EditorTab({
  projectId,
  clips,
  styles,
  assets,
  defaultCaptionStyle,
  defaultReframe,
  onRenderSelected,
  renderPending,
}: EditorTabProps) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Clip[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const next = clips ? clips.clips.map((clip) => ({ ...clip })) : [];
    setDraft(next);
    setSelectedId((current) => {
      if (current && next.some((clip) => clip.id === current)) return current;
      return next.find((clip) => clip.enabled)?.id ?? next[0]?.id ?? null;
    });
    setDirty(false);
  }, [clips]);

  const selected = draft.find((clip) => clip.id === selectedId) ?? null;

  const styleOptions = useMemo(
    () => [
      { value: "", label: "Default" },
      ...styles.map((style) => ({ value: style.key, label: style.label })),
    ],
    [styles],
  );
  const lutOptions = useMemo(
    () => [{ value: "", label: "None" }, ...(assets?.luts ?? []).map((lut) => ({ value: lut, label: lut }))],
    [assets],
  );
  const musicOptions = useMemo(
    () => [
      { value: "", label: "None" },
      ...(assets?.music ?? []).map((track) => ({ value: track, label: track })),
    ],
    [assets],
  );

  const update = (id: string, patch: Partial<Clip>) => {
    setDraft((current) => current.map((clip) => (clip.id === id ? { ...clip, ...patch } : clip)));
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
      toast.success("Edits saved");
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) });
    },
    onError: (error) => toast.error("Could not save edits", { description: errorMessage(error) }),
  });

  const renderSelected = () => {
    if (!selected) {
      toast.warning("Select a clip to render");
      return;
    }
    const inline: ClipList = {
      version: clips?.version ?? 1,
      source: clips?.source ?? {},
      defaults: clips?.defaults ?? {},
      clips: [selected],
    };
    onRenderSelected({
      clips_inline: JSON.stringify(inline),
      caption_style: selected.caption_style ?? null,
      reframe: selected.reframe ?? defaultReframe,
      lut: selected.lut ?? null,
      music: selected.music ?? null,
      platform: "shorts",
      add_titles: true,
      track: true,
    });
  };

  if (!clips || draft.length === 0) {
    return (
      <EmptyState
        icon={<SlidersHorizontal className="h-6 w-6" aria-hidden="true" />}
        title="No clips to edit"
        description="Generate or import clips first, then fine-tune captions, reframing and audio here."
      />
    );
  }

  const resolvedCaption = selected?.caption_style ?? defaultCaptionStyle ?? "default";
  const resolvedReframe = selected?.reframe ?? defaultReframe;
  const resolvedStyle = styles.find((style) => style.key === resolvedCaption) ?? null;
  const captionLabel = resolvedStyle
    ? `${resolvedStyle.label}${resolvedStyle.case ? ` · ${resolvedStyle.case}` : ""}`
    : resolvedCaption;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-label text-muted">
          {draft.length} clips{dirty ? <span className="text-warning"> · unsaved changes</span> : null}
        </p>
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={!dirty}
            loading={saveMutation.isPending}
            leftIcon={<Save className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => saveMutation.mutate()}
          >
            Save edits
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={renderPending}
            disabled={!selected}
            leftIcon={<Video className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={renderSelected}
          >
            Render selected
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card className="max-h-[65vh] overflow-y-auto scrollbar-thin p-1.5">
          <ul className="space-y-0.5">
            {draft.map((clip) => {
              const active = clip.id === selectedId;
              return (
                <li key={clip.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(clip.id)}
                    aria-current={active}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm px-2.5 py-2 text-left transition-colors duration-150 ease-out",
                      active ? "bg-accent/10 text-text" : "text-muted hover:bg-surface-2 hover:text-text",
                    )}
                  >
                    <span
                      className={cn(
                        "h-2 w-2 shrink-0 rounded-full",
                        clip.enabled ? "bg-success" : "bg-muted/50",
                      )}
                      aria-hidden="true"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-body">{clip.title?.trim() || clip.id}</span>
                      <span className="block font-mono text-mono tabular-nums text-muted">
                        {formatClock(clip.start)}–{formatClock(clip.end)} · {formatDuration(clip.end - clip.start)}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>

        {selected ? (
          <Card className="space-y-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="truncate text-title text-text">{selected.title?.trim() || selected.id}</h2>
                <p className="mt-0.5 font-mono text-mono tabular-nums text-muted">
                  {formatClock(selected.start)}–{formatClock(selected.end)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-label text-muted">Enabled</span>
                <Switch
                  checked={selected.enabled}
                  onChange={(checked) => update(selected.id, { enabled: checked })}
                  label={`Enable clip ${selected.id}`}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Caption style">
                <Select
                  value={selected.caption_style ?? ""}
                  options={styleOptions}
                  onChange={(event) => update(selected.id, { caption_style: event.target.value || null })}
                />
              </Field>
              <Field label="Reframe">
                <Select
                  value={selected.reframe ?? ""}
                  options={REFRAME_OPTIONS}
                  onChange={(event) => update(selected.id, { reframe: event.target.value || null })}
                />
              </Field>
              <Field label="LUT">
                <Select
                  value={selected.lut ?? ""}
                  options={lutOptions}
                  onChange={(event) => update(selected.id, { lut: event.target.value || null })}
                />
              </Field>
              <Field label="Music">
                <Select
                  value={selected.music ?? ""}
                  options={musicOptions}
                  onChange={(event) => update(selected.id, { music: event.target.value || null })}
                />
              </Field>
            </div>

            <Field label="Title text" hint="Optional on-screen title.">
              <Input
                value={selected.title_text ?? ""}
                placeholder="On-screen title (optional)"
                onChange={(event) => update(selected.id, { title_text: event.target.value || null })}
              />
            </Field>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-label text-muted">Exclude ranges</span>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<Plus className="h-3.5 w-3.5" aria-hidden="true" />}
                  onClick={() =>
                    update(selected.id, {
                      exclude_ranges: [
                        ...selected.exclude_ranges,
                        [selected.start, selected.start] as [number, number],
                      ],
                    })
                  }
                >
                  Add range
                </Button>
              </div>
              {selected.exclude_ranges.length === 0 ? (
                <p className="text-label text-muted">No excluded ranges.</p>
              ) : (
                <div className="space-y-2">
                  {selected.exclude_ranges.map((range, index) => (
                    <div key={`${selected.id}-${index}`} className="flex items-center gap-2">
                      <Input
                        type="number"
                        step={0.1}
                        value={range[0]}
                        onChange={(event) => {
                          const next: [number, number][] = selected.exclude_ranges.map((item, i) =>
                            i === index
                              ? ([Number(event.target.value), item[1]] as [number, number])
                              : item,
                          );
                          update(selected.id, { exclude_ranges: next });
                        }}
                        className="h-8 w-28 font-mono tabular-nums"
                        aria-label="Exclude start seconds"
                      />
                      <span className="text-label text-muted">to</span>
                      <Input
                        type="number"
                        step={0.1}
                        value={range[1]}
                        onChange={(event) => {
                          const next: [number, number][] = selected.exclude_ranges.map((item, i) =>
                            i === index
                              ? ([item[0], Number(event.target.value)] as [number, number])
                              : item,
                          );
                          update(selected.id, { exclude_ranges: next });
                        }}
                        className="h-8 w-28 font-mono tabular-nums"
                        aria-label="Exclude end seconds"
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Remove range"
                        onClick={() =>
                          update(selected.id, {
                            exclude_ranges: selected.exclude_ranges.filter((_item, i) => i !== index),
                          })
                        }
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-md border border-border bg-surface-2 p-3">
              <p className="mb-1.5 text-label font-medium text-muted">Resolved options</p>
              <dl className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
                {[
                  ["caption_style", captionLabel],
                  ["font", resolvedStyle?.font ?? "default"],
                  ["mode", resolvedStyle?.mode ?? "default"],
                  ["reframe", resolvedReframe],
                  ["lut", selected.lut ?? "none"],
                  ["music", selected.music ?? "none"],
                  ["title_text", selected.title_text?.trim() || "none"],
                  ["exclude_ranges", String(selected.exclude_ranges.length)],
                ].map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between gap-3">
                    <dt className="font-mono text-mono text-muted">{key}</dt>
                    <dd className="truncate font-mono text-mono text-text">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
              <Badge variant={selected.enabled ? "success" : "neutral"}>
                {selected.enabled ? "included" : "excluded"}
              </Badge>
              {selected.keywords.slice(0, 4).map((keyword) => (
                <Badge key={keyword} variant="outline">
                  {keyword}
                </Badge>
              ))}
              {selected.hook ? (
                <Textarea
                  readOnly
                  value={selected.hook}
                  rows={2}
                  className="mt-1 w-full"
                  aria-label="Clip hook"
                />
              ) : null}
            </div>
          </Card>
        ) : (
          <Card className="flex items-center justify-center p-10 text-center">
            <p className="text-label text-muted">Select a clip to edit its options.</p>
          </Card>
        )}
      </div>
    </div>
  );
}

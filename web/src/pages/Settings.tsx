import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";

import { api, queryKeys } from "../lib/api";
import { errorMessage } from "../lib/errors";
import type { Settings, SettingsUpdate } from "../lib/types";
import { ErrorState, LoadingState } from "../components/common/States";
import { CookiesPanel } from "../components/settings/CookiesPanel";
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Field, Input, Select, Switch, useToast } from "../components/ui";

const ENCODERS = [
  { value: "libx264", label: "libx264 (CPU)" },
  { value: "h264_nvenc", label: "h264_nvenc (NVIDIA)" },
];

const PRESETS = [
  { value: "ultrafast", label: "ultrafast" },
  { value: "fast", label: "fast" },
  { value: "medium", label: "medium" },
  { value: "slow", label: "slow" },
];

const REFRAMES = [
  { value: "auto", label: "Auto" },
  { value: "crop", label: "Crop" },
  { value: "blur", label: "Blur" },
  { value: "pad", label: "Pad" },
  { value: "split", label: "Split" },
];

const WHISPER_MODELS = [
  { value: "tiny", label: "tiny" },
  { value: "base", label: "base" },
  { value: "small", label: "small" },
  { value: "medium", label: "medium" },
  { value: "large-v2", label: "large-v2" },
  { value: "large-v3", label: "large-v3" },
];

const COMPUTE_TYPES = [
  { value: "float16", label: "float16" },
  { value: "int8_float16", label: "int8_float16" },
  { value: "int8", label: "int8" },
  { value: "float32", label: "float32" },
];

const DEVICES = [
  { value: "cuda", label: "CUDA (GPU)" },
  { value: "cpu", label: "CPU" },
];

/** The subset of settings owned by this page (CookiesPanel owns the cookie flags). */
function settingsPayload(settings: Settings): SettingsUpdate {
  return {
    render: settings.render,
    default_caption_style: settings.default_caption_style,
    default_reframe: settings.default_reframe,
    whisper_model: settings.whisper_model,
    whisper_compute_type: settings.whisper_compute_type,
    whisper_language: settings.whisper_language,
    transcribe_device: settings.transcribe_device,
  };
}

export default function SettingsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Settings | null>(null);
  const [saved, setSaved] = useState<Settings | null>(null);

  const settingsQuery = useQuery({ queryKey: queryKeys.settings, queryFn: api.getSettings });
  const stylesQuery = useQuery({ queryKey: queryKeys.styles, queryFn: api.styles });

  useEffect(() => {
    if (settingsQuery.data) {
      setDraft(settingsQuery.data);
      setSaved(settingsQuery.data);
    }
  }, [settingsQuery.data]);

  const mutation = useMutation({
    mutationFn: (settings: SettingsUpdate) => api.putSettings(settings),
    onSuccess: (persisted) => {
      queryClient.setQueryData(queryKeys.settings, persisted);
      setDraft(persisted);
      setSaved(persisted);
      toast.success("Settings saved");
    },
    onError: (error) => toast.error("Could not save settings", { description: errorMessage(error) }),
  });

  if (settingsQuery.isLoading || !draft) {
    if (settingsQuery.isError) {
      return (
        <ErrorState
          message={errorMessage(settingsQuery.error)}
          onRetry={() => void settingsQuery.refetch()}
        />
      );
    }
    return <LoadingState label="Loading settings" />;
  }

  const updateRender = <K extends keyof Settings["render"]>(key: K, value: Settings["render"][K]) => {
    setDraft((current) =>
      current ? { ...current, render: { ...current.render, [key]: value } } : current,
    );
  };

  const styleOptions =
    stylesQuery.data?.map((style) => ({ value: style.key, label: style.label })) ?? [];

  const dirty =
    saved != null &&
    JSON.stringify(settingsPayload(draft)) !== JSON.stringify(settingsPayload(saved));

  const save = () => mutation.mutate(settingsPayload(draft));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-display text-text">Settings</h1>
          <p className="mt-1 text-body text-muted">Encoding, transcription, defaults and cookies.</p>
        </div>
        <div className="flex items-center gap-2">
          {dirty ? <Badge variant="warning">Unsaved changes</Badge> : null}
          <Button
            variant="primary"
            disabled={!dirty}
            loading={mutation.isPending}
            leftIcon={<Save className="h-4 w-4" aria-hidden="true" />}
            onClick={save}
          >
            Save settings
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Encoding &amp; performance</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Encoder">
            <Select
              value={draft.render.encoder}
              options={ENCODERS}
              onChange={(event) => updateRender("encoder", event.target.value)}
            />
          </Field>
          <Field label="CRF" hint="Lower is higher quality (0–51).">
            <Input
              type="number"
              min={0}
              max={51}
              value={draft.render.crf}
              onChange={(event) => updateRender("crf", Number(event.target.value))}
              className="font-mono tabular-nums"
            />
          </Field>
          <Field label="Preset">
            <Select
              value={draft.render.preset}
              options={PRESETS}
              onChange={(event) => updateRender("preset", event.target.value)}
            />
          </Field>
          <Field label="Width (px)">
            <Input
              type="number"
              min={1}
              value={draft.render.width}
              onChange={(event) => updateRender("width", Number(event.target.value))}
              className="font-mono tabular-nums"
            />
          </Field>
          <Field label="Height (px)">
            <Input
              type="number"
              min={1}
              value={draft.render.height}
              onChange={(event) => updateRender("height", Number(event.target.value))}
              className="font-mono tabular-nums"
            />
          </Field>
          <Field label="FPS" hint="0 inherits the source frame rate.">
            <Input
              type="number"
              min={0}
              value={draft.render.fps}
              onChange={(event) => updateRender("fps", Number(event.target.value))}
              className="font-mono tabular-nums"
            />
          </Field>
          <Field label="Audio bitrate">
            <Input
              value={draft.render.audio_bitrate}
              onChange={(event) => updateRender("audio_bitrate", event.target.value)}
            />
          </Field>
          <Field label="Loudness (LUFS)" hint="Platform target, e.g. -14.">
            <Input
              type="number"
              step={0.5}
              value={draft.render.audio_lufs}
              onChange={(event) => updateRender("audio_lufs", Number(event.target.value))}
              className="font-mono tabular-nums"
            />
          </Field>
          <div className="flex items-center justify-between gap-3 self-end rounded-md border border-border bg-surface-2 px-3.5 py-2.5">
            <span className="text-body text-text">Faststart</span>
            <Switch
              checked={draft.render.faststart}
              onChange={(checked) => updateRender("faststart", checked)}
              label="Faststart"
            />
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Transcription</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Whisper model">
            <Select
              value={draft.whisper_model}
              options={WHISPER_MODELS}
              onChange={(event) => setDraft({ ...draft, whisper_model: event.target.value })}
            />
          </Field>
          <Field label="Compute type">
            <Select
              value={draft.whisper_compute_type}
              options={COMPUTE_TYPES}
              onChange={(event) => setDraft({ ...draft, whisper_compute_type: event.target.value })}
            />
          </Field>
          <Field label="Device">
            <Select
              value={draft.transcribe_device}
              options={DEVICES}
              onChange={(event) => setDraft({ ...draft, transcribe_device: event.target.value })}
            />
          </Field>
          <Field label="Language" hint="Blank auto-detects.">
            <Input
              value={draft.whisper_language ?? ""}
              placeholder="auto"
              onChange={(event) =>
                setDraft({ ...draft, whisper_language: event.target.value.trim() || null })
              }
            />
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Defaults</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Default caption style">
            {styleOptions.length > 0 ? (
              <Select
                value={draft.default_caption_style}
                options={styleOptions}
                onChange={(event) => setDraft({ ...draft, default_caption_style: event.target.value })}
              />
            ) : (
              <Input
                value={draft.default_caption_style}
                onChange={(event) => setDraft({ ...draft, default_caption_style: event.target.value })}
              />
            )}
          </Field>
          <Field label="Default reframe">
            <Select
              value={draft.default_reframe}
              options={REFRAMES}
              onChange={(event) => setDraft({ ...draft, default_reframe: event.target.value })}
            />
          </Field>
        </CardBody>
      </Card>

      <CookiesPanel />
    </div>
  );
}

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, ExternalLink } from "lucide-react";

import { api, queryKeys } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { formatClock } from "../../lib/format";
import type { ClipList, ProjectText } from "../../lib/types";
import { CopyButton } from "../common/CopyButton";
import { ErrorState, LoadingState } from "../common/States";
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Field,
  Segmented,
  Textarea,
  useToast,
} from "../ui";

type TextTab = "transcript" | "payload" | "prompt" | "srt";

const TABS = [
  { value: "transcript", label: "Transcript" },
  { value: "payload", label: "Payload" },
  { value: "prompt", label: "Prompt" },
  { value: "srt", label: "SRT" },
];

function valueFor(text: ProjectText | undefined, tab: TextTab): string | null {
  if (!text) return null;
  switch (tab) {
    case "transcript":
      return text.txt;
    case "payload":
      return text.payload;
    case "prompt":
      return text.prompt;
    case "srt":
      return text.srt;
  }
}

export function TranscriptTab({ projectId }: { projectId: string }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<TextTab>("transcript");
  const [importText, setImportText] = useState("");
  const [lastImport, setLastImport] = useState<ClipList | null>(null);

  const textQuery = useQuery({
    queryKey: queryKeys.text(projectId),
    queryFn: () => api.text(projectId),
    enabled: Boolean(projectId),
  });

  const importMutation = useMutation({
    mutationFn: () => api.importClips(projectId, { inline: importText }),
    onSuccess: (clips) => {
      setLastImport(clips);
      toast.success(`Validated ${clips.clips.length} clips`);
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) });
    },
    onError: (error) => {
      setLastImport(null);
      toast.error("Import failed", { description: errorMessage(error) });
    },
  });

  const current = valueFor(textQuery.data, tab);

  const openCombined = useMemo(
    () => () => {
      const payload = textQuery.data?.payload ?? "";
      const prompt = textQuery.data?.prompt ?? "";
      const combined = [
        payload ? `# PAYLOAD\n\n${payload}` : "",
        prompt ? `# PROMPT\n\n${prompt}` : "",
      ]
        .filter(Boolean)
        .join("\n\n---\n\n");
      const blob = new Blob([combined], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    },
    [textQuery.data],
  );

  if (textQuery.isLoading) {
    return <LoadingState label="Loading transcript" />;
  }
  if (textQuery.isError) {
    return (
      <ErrorState message={errorMessage(textQuery.error)} onRetry={() => void textQuery.refetch()} />
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
          <Segmented
            aria-label="Text output"
            size="sm"
            options={TABS}
            value={tab}
            onChange={(value) => setTab(value as TextTab)}
          />
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />}
              onClick={openCombined}
            >
              Open payload + prompt
            </Button>
            <CopyButton text={current ?? ""} disabled={!current} />
          </div>
        </div>
        <CardBody className="p-0">
          {current ? (
            <pre className="max-h-[60vh] overflow-auto scrollbar-thin whitespace-pre-wrap break-words px-4 py-3 font-mono text-mono text-text">
              {current}
            </pre>
          ) : (
            <div className="px-4 py-12 text-center text-label text-muted">
              No {tab} yet. Run analysis to generate it, or import clips below.
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Import clips</CardTitle>
          <span className="text-label text-muted">JSON or CSV</span>
        </CardHeader>
        <CardBody className="space-y-3">
          <Field
            label="Paste clip data"
            hint="Accepts a JSON ClipList, a bare JSON array of clips, or CSV with title,start,end columns."
          >
            <Textarea
              value={importText}
              onChange={(event) => setImportText(event.target.value)}
              placeholder={'[{"title":"Intro hook","start":"00:12","end":"00:46"}]'}
              rows={7}
            />
          </Field>

          {importMutation.isError ? (
            <Alert tone="danger" title="Could not validate clips">
              <p className="whitespace-pre-wrap break-words font-mono text-mono">
                {errorMessage(importMutation.error)}
              </p>
            </Alert>
          ) : lastImport ? (
            <Alert tone="success" title={`Validated ${lastImport.clips.length} clips`}>
              <p className="text-muted">
                Normalized to version {lastImport.version}. Review before rendering.
              </p>
              <ul className="mt-1 space-y-0.5">
                {lastImport.clips.slice(0, 8).map((clip) => (
                  <li key={clip.id} className="flex items-center gap-2 font-mono text-mono">
                    <span className="text-text">{clip.title?.trim() || clip.id}</span>
                    <span className="text-muted">
                      {formatClock(clip.start)}–{formatClock(clip.end)}
                    </span>
                  </li>
                ))}
                {lastImport.clips.length > 8 ? (
                  <li className="text-muted">+{lastImport.clips.length - 8} more</li>
                ) : null}
              </ul>
            </Alert>
          ) : (
            <p className="text-label text-muted">Nothing validated yet.</p>
          )}

          <div className="flex items-center justify-end gap-3">
            <Button
              variant="primary"
              size="sm"
              loading={importMutation.isPending}
              disabled={!importText.trim()}
              leftIcon={<BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" />}
              onClick={() => importMutation.mutate()}
            >
              Validate
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

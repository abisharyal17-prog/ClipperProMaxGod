import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { api } from "../lib/api";
import { errorMessage } from "../lib/errors";
import type { ProjectSummary } from "../lib/types";
import { Button, Dialog, Field, Input, useToast } from "./ui";

export interface NewProjectDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (project: ProjectSummary) => void;
}

export function NewProjectDialog({ open, onClose, onCreated }: NewProjectDialogProps) {
  const toast = useToast();
  const [source, setSource] = useState("");
  const [id, setId] = useState("");
  const [cookies, setCookies] = useState("");
  const [showError, setShowError] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      api.createProject({
        source: source.trim(),
        ...(id.trim() ? { id: id.trim() } : {}),
        ...(cookies.trim() ? { cookies: cookies.trim() } : {}),
      }),
    onSuccess: (project) => {
      toast.success("Project created", { description: project.id });
      setSource("");
      setId("");
      setCookies("");
      setShowError(false);
      onCreated(project);
    },
    onError: (error) => toast.error("Could not create project", { description: errorMessage(error) }),
  });

  const submit = () => {
    if (!source.trim()) {
      setShowError(true);
      return;
    }
    mutation.mutate();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New project"
      description="Ingest a video by URL or local path. Transcription and analysis run separately."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="new-project-form"
            variant="primary"
            loading={mutation.isPending}
          >
            Create project
          </Button>
        </>
      }
    >
      <form
        id="new-project-form"
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <Field
          label="Source"
          hint="YouTube/TikTok URL or a local file path."
          error={showError && !source.trim() ? "A source URL or path is required." : undefined}
        >
          <Input
            autoFocus
            value={source}
            onChange={(event) => {
              setSource(event.target.value);
              if (showError) setShowError(false);
            }}
            placeholder="https://youtube.com/watch?v=..."
            required
          />
        </Field>
        <Field label="Project id" hint="Optional. Defaults to a generated id.">
          <Input
            value={id}
            onChange={(event) => setId(event.target.value)}
            placeholder="my-episode-01"
          />
        </Field>
        <Field label="Cookies from browser" hint="Optional. e.g. chrome, firefox — for gated videos.">
          <Input
            value={cookies}
            onChange={(event) => setCookies(event.target.value)}
            placeholder="chrome"
          />
        </Field>
      </form>
    </Dialog>
  );
}

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, FileCheck2, Save, ShieldCheck, Trash2 } from "lucide-react";

import { api, queryKeys } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { formatDays } from "../../lib/format";
import { cookieHealth, useCookieStatus } from "../../hooks/useCookieStatus";
import type { CookieVerifyResult } from "../../lib/types";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Dialog,
  Field,
  Select,
  StatusDot,
  Switch,
  Textarea,
  useToast,
} from "../ui";
import type { AlertTone } from "../ui";

const BROWSERS = [
  { value: "chrome", label: "Chrome" },
  { value: "firefox", label: "Firefox" },
  { value: "edge", label: "Edge" },
  { value: "brave", label: "Brave" },
];

function warningTone(warning: string): AlertTone {
  const lower = warning.toLowerCase();
  if (lower.includes("expired") || lower.includes("unauthenticated")) return "danger";
  return "warning";
}

function statusSummary(
  present: boolean,
  count: number,
  authenticated: boolean,
  daysLeft: number | null,
): string {
  if (!present) return "No cookies configured";
  const parts: string[] = [`${count} cookies`];
  parts.push(authenticated ? "authenticated" : "unauthenticated");
  if (daysLeft != null) parts.push(`expires in ${formatDays(daysLeft)}`);
  return parts.join(" · ");
}

export function CookiesPanel() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const cookieQuery = useCookieStatus();
  const settingsQuery = useQuery({ queryKey: queryKeys.settings, queryFn: api.getSettings });

  const [importText, setImportText] = useState("");
  const [profile, setProfile] = useState("chrome");
  const [verifyResult, setVerifyResult] = useState<CookieVerifyResult | null>(null);
  const [clearOpen, setClearOpen] = useState(false);

  useEffect(() => {
    const fromBrowser = settingsQuery.data?.cookies_from_browser;
    if (fromBrowser) setProfile(fromBrowser);
  }, [settingsQuery.data?.cookies_from_browser]);

  const cookies = cookieQuery.data;
  const health = cookieHealth(cookies);

  const applyStatus = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.cookies });
    void queryClient.invalidateQueries({ queryKey: queryKeys.settings });
  };

  const importMutation = useMutation({
    mutationFn: () => api.importCookies({ content: importText }),
    onSuccess: () => {
      setImportText("");
      applyStatus();
      toast.success("Cookies imported");
    },
    onError: (error) => toast.error("Could not import cookies", { description: errorMessage(error) }),
  });

  const browserMutation = useMutation({
    mutationFn: () => api.importCookies({ from_browser: profile }),
    onSuccess: () => {
      applyStatus();
      toast.success("Browser profile saved");
    },
    onError: (error) => toast.error("Could not save profile", { description: errorMessage(error) }),
  });

  const useCookiesMutation = useMutation({
    mutationFn: (enabled: boolean) => api.putSettings({ use_cookies: enabled }),
    onSuccess: () => applyStatus(),
    onError: (error) => toast.error("Could not update setting", { description: errorMessage(error) }),
  });

  const verifyMutation = useMutation({
    mutationFn: () => api.verifyCookies(),
    onSuccess: (result) => {
      setVerifyResult(result);
      queryClient.setQueryData(queryKeys.cookies, result.status);
      if (result.ok) toast.success("Cookies verified");
      else toast.warning("Verification failed", { description: result.message });
    },
    onError: (error) => toast.error("Could not verify cookies", { description: errorMessage(error) }),
  });

  const clearMutation = useMutation({
    mutationFn: () => api.clearCookies(),
    onSuccess: () => {
      setClearOpen(false);
      setVerifyResult(null);
      applyStatus();
      toast.success("Cookies cleared");
    },
    onError: (error) => toast.error("Could not clear cookies", { description: errorMessage(error) }),
  });

  const tone =
    health === "ok" ? "success" : health === "danger" ? "danger" : health === "warning" ? "warning" : "neutral";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cookies</CardTitle>
        <Badge variant={tone === "neutral" ? "neutral" : tone}>
          {health === "ok" ? "healthy" : health === "unknown" ? "unknown" : "attention"}
        </Badge>
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="flex items-center gap-2" role="status" aria-live="polite">
          <StatusDot tone={tone === "neutral" ? "neutral" : tone} />
          <span className="text-body text-text">
            {cookieQuery.isLoading
              ? "Checking cookie status…"
              : statusSummary(
                  cookies?.present ?? false,
                  cookies?.count ?? 0,
                  cookies?.authenticated ?? false,
                  cookies?.days_left ?? null,
                )}
          </span>
        </div>

        {cookieQuery.isError ? (
          <Alert
            tone="danger"
            title="Could not load cookie status"
            actions={
              <Button variant="secondary" size="sm" onClick={() => void cookieQuery.refetch()}>
                Retry
              </Button>
            }
          >
            {errorMessage(cookieQuery.error)}
          </Alert>
        ) : null}

        {cookies?.warnings.map((warning) => (
          <Alert key={warning} tone={warningTone(warning)}>
            {warning}
          </Alert>
        ))}

        <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-2 px-3.5 py-3">
          <div>
            <p className="text-body text-text">Use cookies for ingest</p>
            <p className="text-label text-muted">Applied automatically to every project.</p>
          </div>
          <Switch
            checked={settingsQuery.data?.use_cookies ?? true}
            disabled={!settingsQuery.data || useCookiesMutation.isPending}
            onChange={(checked) => useCookiesMutation.mutate(checked)}
            label="Use cookies for ingest"
          />
        </div>

        <Field
          label="Paste cookie JSON or Netscape cookies.txt"
          hint="Values are never displayed. A cookie-editor export or raw Netscape file both work."
        >
          <Textarea
            value={importText}
            onChange={(event) => setImportText(event.target.value)}
            rows={6}
            placeholder="Paste cookie JSON or Netscape cookies.txt contents"
          />
        </Field>
        <div className="flex justify-end">
          <Button
            variant="primary"
            size="sm"
            loading={importMutation.isPending}
            disabled={!importText.trim()}
            leftIcon={<FileCheck2 className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => importMutation.mutate()}
          >
            Import
          </Button>
        </div>

        <div className="grid gap-3 border-t border-border pt-4 sm:grid-cols-[1fr_auto] sm:items-end">
          <Field label="Use browser profile" hint="Fallback: read cookies directly from a local browser.">
            <Select
              value={profile}
              options={BROWSERS}
              onChange={(event) => setProfile(event.target.value)}
            />
          </Field>
          <Button
            variant="secondary"
            size="sm"
            loading={browserMutation.isPending}
            leftIcon={<Globe className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => browserMutation.mutate()}
          >
            Save
          </Button>
        </div>

        {verifyResult ? (
          <Alert
            tone={verifyResult.ok ? "success" : "danger"}
            title={verifyResult.message}
          >
            {verifyResult.detail ? (
              <pre className="mt-1 max-h-32 overflow-auto scrollbar-thin whitespace-pre-wrap break-words font-mono text-mono">
                {verifyResult.detail}
              </pre>
            ) : null}
          </Alert>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <Button
            variant="secondary"
            size="sm"
            loading={verifyMutation.isPending}
            disabled={!cookies?.present}
            leftIcon={<ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => verifyMutation.mutate()}
          >
            Verify
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={!cookies?.present}
            leftIcon={<Trash2 className="h-3.5 w-3.5" aria-hidden="true" />}
            onClick={() => setClearOpen(true)}
          >
            Clear
          </Button>
          <span className="ml-auto inline-flex items-center gap-1.5 text-label text-muted">
            <Save className="h-3 w-3" aria-hidden="true" />
            Stored server-side, shared by all projects
          </span>
        </div>
      </CardBody>

      <Dialog
        open={clearOpen}
        onClose={() => setClearOpen(false)}
        title="Clear cookies"
        description="Remove the stored cookie file. Gated or age-restricted videos may fail until you re-import."
        footer={
          <>
            <Button variant="ghost" onClick={() => setClearOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={clearMutation.isPending}
              onClick={() => clearMutation.mutate()}
            >
              Clear cookies
            </Button>
          </>
        }
      />
    </Card>
  );
}

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { KeyRound, Laptop, Loader2, RefreshCw, ShieldCheck, Terminal } from "lucide-react";

import { UNAUTHORIZED_EVENT } from "../../lib/api";
import {
  ENGINE_HOST_LABEL,
  INSTALL_COMMAND,
  SETUP_DOCS_URL,
  adoptTokenFromLocation,
  getToken,
  probeEngine,
  setToken,
  type EngineProbe,
} from "../../lib/engine";
import { CopyButton } from "./CopyButton";
import { Alert, Button, Card, CardBody, Field, Input } from "../ui";

type Phase = { kind: "checking" } | { kind: "probe"; probe: EngineProbe };

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-xl space-y-5">
        <div className="flex items-center gap-2 text-text">
          <Laptop className="h-5 w-5 text-accent" aria-hidden="true" />
          <span className="text-title font-semibold">Clipper</span>
        </div>
        {children}
      </div>
    </div>
  );
}

export function EngineGate({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>({ kind: "checking" });
  const [tokenDraft, setTokenDraft] = useState("");
  const [pairing, setPairing] = useState(false);

  const refresh = useCallback(async () => {
    const probe = await probeEngine();
    setPhase({ kind: "probe", probe });
  }, []);

  const initial = useCallback(async () => {
    setPhase({ kind: "checking" });
    adoptTokenFromLocation();
    await refresh();
  }, [refresh]);

  useEffect(() => {
    void initial();
  }, [initial]);

  useEffect(() => {
    const handler = () => void refresh();
    window.addEventListener(UNAUTHORIZED_EVENT, handler);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handler);
  }, [refresh]);

  // Poll until the engine appears / the token is accepted, so the tab "lights up"
  // on its own once the one-line setup finishes.
  useEffect(() => {
    if (phase.kind !== "probe" || phase.probe.status === "ready") return;
    const id = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(id);
  }, [phase, refresh]);

  const pair = async () => {
    if (!tokenDraft.trim()) return;
    setPairing(true);
    setToken(tokenDraft);
    setTokenDraft("");
    await refresh();
    setPairing(false);
  };

  if (phase.kind === "checking") {
    return (
      <Shell>
        <Card>
          <CardBody className="flex items-center gap-3 py-8 text-body text-muted">
            <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden="true" />
            Looking for the Clipper engine on this computer…
          </CardBody>
        </Card>
      </Shell>
    );
  }

  if (phase.probe.status === "ready") {
    return <>{children}</>;
  }

  if (phase.probe.status === "needs-token") {
    return (
      <Shell>
        <Alert tone="info" title="The engine is running on this computer">
          It needs your access token before the app can connect.
        </Alert>
        <Card>
          <CardBody className="space-y-4">
            <div className="flex items-center gap-2 text-body font-medium text-text">
              <KeyRound className="h-4 w-4 text-accent" aria-hidden="true" />
              Pair this browser
            </div>
            <Field
              label="Engine token"
              hint="Printed in the engine window when it started, and copied to your clipboard."
            >
              <div className="flex gap-2">
                <Input
                  value={tokenDraft}
                  onChange={(event) => setTokenDraft(event.target.value)}
                  placeholder="Paste token…"
                  autoComplete="off"
                  spellCheck={false}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void pair();
                  }}
                />
                <Button
                  variant="primary"
                  onClick={() => void pair()}
                  loading={pairing}
                  disabled={!tokenDraft.trim()}
                >
                  Pair
                </Button>
              </div>
            </Field>
            <div className="flex items-center gap-2 text-label text-muted">
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
              The token stays in this browser and is only sent to your own engine.
            </div>
          </CardBody>
        </Card>
        <div className="flex justify-center">
          <Button variant="ghost" size="sm" leftIcon={<RefreshCw className="h-3.5 w-3.5" />} onClick={() => void refresh()}>
            Check again
          </Button>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <Alert tone="warning" title="The Clipper engine isn't running on this computer">
        Clipper processes video on your own machine, so it needs a small local engine. Set it up once
        with the command below — this page will connect on its own.
      </Alert>

      <Card>
        <CardBody className="space-y-5">
          <ol className="space-y-4">
            <li className="space-y-2">
              <p className="text-body text-text">
                <span className="text-muted">1.</span> Open <strong className="font-medium">PowerShell</strong>{" "}
                <span className="text-muted">(press Win, type “PowerShell”, press Enter)</span>
              </p>
            </li>
            <li className="space-y-2">
              <p className="text-body text-text">
                <span className="text-muted">2.</span> Paste this and press Enter
              </p>
              {INSTALL_COMMAND ? (
                <div className="flex items-start gap-2">
                  <pre className="min-w-0 flex-1 overflow-x-auto rounded-sm border border-border bg-surface-2 px-3 py-2 font-mono text-mono text-text">
                    {INSTALL_COMMAND}
                  </pre>
                  <CopyButton text={INSTALL_COMMAND} />
                </div>
              ) : (
                <Alert tone="info">
                  The install command isn’t configured in this build. See the setup guide to install
                  the engine manually.
                </Alert>
              )}
            </li>
            <li className="space-y-2">
              <p className="text-body text-text">
                <span className="text-muted">3.</span> Leave that window open while you use Clipper
              </p>
              <p className="text-label text-muted">
                When it’s ready it opens this page with a one-time link and pairs automatically.
              </p>
            </li>
          </ol>

          <div className="flex items-center gap-3 border-t border-border pt-4 text-label text-muted">
            <Terminal className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Looking for the engine at <code className="font-mono text-mono">{ENGINE_HOST_LABEL}</code>…
          </div>
        </CardBody>
      </Card>

      <div className="flex items-center justify-center gap-2">
        <Button variant="secondary" size="sm" leftIcon={<RefreshCw className="h-3.5 w-3.5" />} onClick={() => void refresh()}>
          Check again
        </Button>
        {SETUP_DOCS_URL ? (
          <a
            href={SETUP_DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="text-label font-medium text-accent transition-colors duration-150 ease-out hover:underline"
          >
            Setup guide
          </a>
        ) : null}
        {getToken() ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setToken(null);
              void refresh();
            }}
          >
            Clear saved token
          </Button>
        ) : null}
      </div>
    </Shell>
  );
}

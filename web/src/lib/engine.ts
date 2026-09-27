import type { HealthResponse } from "./types";

/**
 * Where the local engine lives and how to pair with it.
 *
 * When the UI is hosted (e.g. on Vercel) it talks to the engine on the user's
 * own machine, so the base URL defaults to `http://127.0.0.1:8765`. In local dev
 * `VITE_API_BASE` overrides it (e.g. a Vite proxy or a different port).
 */
const RAW_BASE = (import.meta.env.VITE_API_BASE ?? "").trim();

export const ENGINE_BASE = (RAW_BASE || "http://127.0.0.1:8765").replace(/\/+$/, "");
export const ENGINE_HOST_LABEL = ENGINE_BASE.replace(/^https?:\/\//, "");

const TOKEN_KEY = "clipper.engine.token";
let memoryToken: string | null = null;

/** The install command shown when no engine is detected (configurable at build time). */
const INSTALL_SCRIPT_URL = (import.meta.env.VITE_INSTALL_SCRIPT ?? "").trim();
export const INSTALL_COMMAND = INSTALL_SCRIPT_URL ? `irm ${INSTALL_SCRIPT_URL} | iex` : "";
export const SETUP_DOCS_URL = (import.meta.env.VITE_SETUP_DOCS ?? "").trim();

export function getToken(): string | null {
  if (memoryToken) return memoryToken;
  try {
    memoryToken = window.localStorage.getItem(TOKEN_KEY);
  } catch {
    memoryToken = null;
  }
  return memoryToken;
}

export function setToken(token: string | null): void {
  memoryToken = token && token.trim() ? token.trim() : null;
  try {
    if (memoryToken) window.localStorage.setItem(TOKEN_KEY, memoryToken);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage may be unavailable (private mode) - the in-memory copy still works */
  }
}

/**
 * Read a token handed over in the URL fragment (`#token=...`) or query string,
 * persist it, then strip it from the address bar. Fragments never reach a
 * server, so hosting the UI does not leak the token.
 */
export function adoptTokenFromLocation(): string | null {
  const hash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  const hashParams = new URLSearchParams(hash);
  const searchParams = new URLSearchParams(window.location.search);
  const token = hashParams.get("token") ?? searchParams.get("token");
  if (!token) return null;

  setToken(token);
  hashParams.delete("token");
  searchParams.delete("token");
  const query = searchParams.toString();
  const fragment = hashParams.toString();
  window.history.replaceState(
    null,
    "",
    window.location.pathname + (query ? `?${query}` : "") + (fragment ? `#${fragment}` : ""),
  );
  return token;
}

async function fetchWithTimeout(url: string, init: RequestInit, ms: number): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

export type EngineProbe =
  | { status: "unreachable"; message: string }
  | { status: "needs-token"; health: HealthResponse }
  | { status: "ready"; health: HealthResponse };

export async function verifyToken(ms = 2500): Promise<boolean> {
  const token = getToken();
  if (!token) return false;
  try {
    const response = await fetchWithTimeout(
      `${ENGINE_BASE}/api/auth/verify`,
      { headers: { Authorization: `Bearer ${token}` } },
      ms,
    );
    return response.ok;
  } catch {
    return false;
  }
}

export async function probeEngine(ms = 2500): Promise<EngineProbe> {
  let health: HealthResponse;
  try {
    const response = await fetchWithTimeout(`${ENGINE_BASE}/api/health`, {}, ms);
    if (!response.ok) {
      return { status: "unreachable", message: `Engine responded with ${response.status}.` };
    }
    health = (await response.json()) as HealthResponse;
  } catch (cause) {
    const message =
      cause instanceof DOMException && cause.name === "AbortError"
        ? "The engine did not respond in time."
        : "Could not reach the local engine.";
    return { status: "unreachable", message };
  }

  if (!health.auth_required) return { status: "ready", health };
  if (!getToken()) return { status: "needs-token", health };
  return (await verifyToken(ms)) ? { status: "ready", health } : { status: "needs-token", health };
}

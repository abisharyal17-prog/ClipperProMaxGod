import type {
  AnalysisOptions,
  Assets,
  CaptionStyle,
  ClipList,
  CookieStatus,
  CookieVerifyResult,
  Graph,
  HealthResponse,
  Job,
  JobStage,
  MetadataPack,
  NodeType,
  ProjectDetail,
  ProjectSummary,
  ProjectText,
  RenderOptions,
  Settings,
  SettingsUpdate,
} from "./types";

import { ENGINE_BASE, getToken } from "./engine";

/** Absolute base for the engine (hosted UI -> 127.0.0.1, else same-origin/Vite proxy). */
export const API_BASE = ENGINE_BASE;

/** Name of the window event fired when the engine rejects our token (401). */
export const UNAUTHORIZED_EVENT = "clipper:unauthorized";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function messageFromDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const value = record.detail ?? record.message ?? record.error;
    if (typeof value === "string" && value.trim()) return value;
    if (Array.isArray(value) && value.length > 0) {
      const first = value[0] as Record<string, unknown> | undefined;
      if (first && typeof first.msg === "string") return first.msg;
    }
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch (cause) {
    throw new ApiError(
      `Cannot reach the Clipper server (${path}).`,
      0,
      cause instanceof Error ? cause.message : cause,
    );
  }

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
  }

  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(
      messageFromDetail(parsed, `${response.status} ${response.statusText}`),
      response.status,
      parsed,
    );
  }
  return parsed as T;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  nodes: () => request<NodeType[]>("/api/nodes"),
  styles: () => request<CaptionStyle[]>("/api/styles"),
  assets: () => request<Assets>("/api/assets"),

  getSettings: () => request<Settings>("/api/settings"),
  putSettings: (settings: SettingsUpdate) =>
    request<Settings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),

  cookies: () => request<CookieStatus>("/api/cookies"),
  importCookies: (body: { content?: string; from_browser?: string; source?: string }) =>
    post<CookieStatus>("/api/cookies", body),
  clearCookies: () => request<CookieStatus>("/api/cookies", { method: "DELETE" }),
  verifyCookies: () => post<CookieVerifyResult>("/api/cookies/verify"),

  projects: () => request<ProjectSummary[]>("/api/projects"),
  createProject: (body: { source: string; id?: string; cookies?: string }) =>
    post<ProjectSummary>("/api/projects", body),
  project: (id: string) => request<ProjectDetail>(`/api/projects/${encodeURIComponent(id)}`),
  deleteProject: (id: string) =>
    request<{ ok: boolean }>(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" }),

  graph: (id: string, stage: JobStage) =>
    request<Graph>(`/api/projects/${encodeURIComponent(id)}/graph?stage=${stage}`),

  text: (id: string) => request<ProjectText>(`/api/projects/${encodeURIComponent(id)}/text`),

  putClips: (id: string, clips: ClipList) =>
    request<ClipList>(`/api/projects/${encodeURIComponent(id)}/clips`, {
      method: "PUT",
      body: JSON.stringify(clips),
    }),
  importClips: (id: string, body: { inline?: string; path?: string }) =>
    post<ClipList>(`/api/projects/${encodeURIComponent(id)}/clips/import`, body),

  metadata: (id: string) =>
    request<MetadataPack>(`/api/projects/${encodeURIComponent(id)}/metadata`),

  createJob: (id: string, body: { stage: JobStage; options?: RenderOptions | AnalysisOptions }) =>
    post<Job>(`/api/projects/${encodeURIComponent(id)}/jobs`, body),
  jobs: (id: string) => request<Job[]>(`/api/projects/${encodeURIComponent(id)}/jobs`),
  job: (jobId: string) => request<Job>(`/api/jobs/${encodeURIComponent(jobId)}`),
  cancelJob: (jobId: string) =>
    post<Job>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`),
};

/** Absolute URL for a `/media/...` path (respects VITE_API_BASE, else same origin). */
export function mediaUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (/^https?:\/\//i.test(path) || path.startsWith("data:")) return path;
  const suffix = path.startsWith("/") ? path : `/${path}`;
  const token = getToken();
  const separator = suffix.includes("?") ? "&" : "?";
  const auth = token ? `${separator}token=${encodeURIComponent(token)}` : "";
  return `${API_BASE}${suffix}${auth}`;
}

export function jobSocketUrl(jobId: string): string {
  const token = getToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  if (API_BASE) {
    const url = new URL(API_BASE, window.location.origin);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return `${url.origin}/ws/jobs/${encodeURIComponent(jobId)}${query}`;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/jobs/${encodeURIComponent(jobId)}${query}`;
}

export const queryKeys = {
  health: ["health"] as const,
  nodes: ["nodes"] as const,
  styles: ["styles"] as const,
  assets: ["assets"] as const,
  settings: ["settings"] as const,
  cookies: ["cookies"] as const,
  projects: ["projects"] as const,
  project: (id: string) => ["project", id] as const,
  graph: (id: string, stage: JobStage) => ["graph", id, stage] as const,
  text: (id: string) => ["text", id] as const,
  metadata: (id: string) => ["metadata", id] as const,
  jobs: (id: string) => ["jobs", id] as const,
};

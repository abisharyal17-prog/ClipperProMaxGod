export type JobStage = "analysis" | "render";
export type JobStatus = "queued" | "running" | "done" | "error" | "cancelled";
export type JobLevel = "info" | "warn" | "error";

export interface ToolStatus {
  ffmpeg: string | null;
  ffprobe: string | null;
  ytdlp: string | null;
  cuda: boolean;
  whisper: boolean;
  tracker: boolean;
}

export interface HealthResponse {
  status: string;
  name?: string;
  version: string;
  auth_required?: boolean;
  tools: ToolStatus;
}

export interface NodeType {
  type: string;
  title: string;
  category: string;
  description: string;
  inputs: Record<string, string>;
  outputs: Record<string, string>;
  params_schema: Record<string, unknown>;
}

export interface CaptionStyle {
  key: string;
  label: string;
  font: string;
  mode: string;
  font_size: number;
  position: number;
  /** Case transform ("upper" | "sentence" | ...). Optional for forward-compat. */
  case?: string;
}

export interface Assets {
  luts: string[];
  music: string[];
  fonts: string[];
}

export interface ProjectSummary {
  id: string;
  created: string;
  modified: string;
  source: string | null;
  title: string | null;
  has_source: boolean;
  has_transcript: boolean;
  has_clips: boolean;
  clip_count: number;
  render_count: number;
  thumbnail: string | null;
}

export interface Clip {
  id: string;
  title: string | null;
  start: number;
  end: number;
  score: number | null;
  reason: string | null;
  hook: string | null;
  keywords: string[];
  reframe: string | null;
  caption_style: string | null;
  lut: string | null;
  music: string | null;
  title_text: string | null;
  enabled: boolean;
  exclude_ranges: [number, number][];
  loop_ending: boolean | null;
}

export interface ClipList {
  version: number;
  source: Record<string, unknown>;
  defaults: Record<string, unknown>;
  clips: Clip[];
}

export interface Render {
  clip_id: string;
  path: string;
  duration: number;
  title: string | null;
  reframe: string;
  camera: string;
  url: string;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface TranscriptWord {
  start: number;
  end: number;
  word: string;
}

export interface Transcript {
  language: string | null;
  duration: number;
  segments: TranscriptSegment[];
  words: TranscriptWord[];
}

export interface ProjectEvents {
  lufs: number | null;
  silences: [number, number][];
}

export interface ProjectScenes {
  count: number;
  cuts: number[];
}

export interface ProjectDetail {
  summary: ProjectSummary;
  transcript: Transcript | null;
  events: ProjectEvents | null;
  scenes: ProjectScenes | null;
  clips: ClipList | null;
  renders: Render[];
  defaults: Record<string, unknown>;
}

export interface ProjectText {
  txt: string | null;
  srt: string | null;
  payload: string | null;
  prompt: string | null;
}

export interface MetadataPack {
  metadata: Record<string, unknown>;
  markdown: string;
}

export interface JobEvent {
  type: string;
  node: string | null;
  pct: number | null;
  message: string;
  level: JobLevel;
  ts: number;
  cached?: boolean;
}

export interface Job {
  id: string;
  project_id: string;
  stage: JobStage;
  status: JobStatus;
  error: string | null;
  created: number;
  events: JobEvent[];
  result: Record<string, unknown> | null;
}

export interface GraphNodeData {
  label?: string;
  title: string;
  category: string;
  params: Record<string, unknown>;
  inputs: Record<string, string>;
  outputs: Record<string, string>;
}

export interface GraphNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: GraphNodeData;
  ui?: { x?: number; y?: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  animated?: boolean;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface RenderSettings {
  width: number;
  height: number;
  fps: number;
  encoder: string;
  crf: number;
  preset: string;
  audio_bitrate: string;
  audio_lufs: number;
  faststart: boolean;
}

export interface Settings {
  render: RenderSettings;
  default_caption_style: string;
  default_reframe: string;
  whisper_model: string;
  whisper_compute_type: string;
  whisper_language: string | null;
  transcribe_device: string;
  use_cookies: boolean;
  cookies_from_browser: string | null;
}

export type SettingsUpdate = Partial<Omit<Settings, "render">> & {
  render?: Partial<RenderSettings>;
};

export interface RenderOptions {
  clips_path?: string | null;
  clips_inline?: string | null;
  caption_style?: string | null;
  reframe?: string;
  lut?: string | null;
  music?: string | null;
  platform?: string;
  add_titles?: boolean;
  track?: boolean;
}

export interface AnalysisOptions {
  n_clips?: number;
  min_duration?: number;
  max_duration?: number;
  cookies?: string | null;
}

/** Global cookie store status (WEBSPEC §7). */
export interface CookieStatus {
  present: boolean;
  count: number;
  session_cookies: number;
  authenticated: boolean;
  updated: string | null;
  source: string | null;
  earliest_expiry: number | null;
  days_left: number | null;
  expired: boolean;
  expiring_soon: boolean;
  warnings: string[];
}

export interface CookieVerifyResult {
  ok: boolean;
  message: string;
  detail: string;
  status: CookieStatus;
}

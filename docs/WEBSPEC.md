# Clipper Web — API + UI contract (v1)

Authoritative contract for the local web app. Backend: FastAPI (`app/api`).
Frontend: Vite + React + TS + Tailwind + `@xyflow/react` (`web/`).
Backend serves the built frontend (`web/dist`) at `/`.

Server: `http://127.0.0.1:8765`. All JSON. CORS not needed (same origin) but allow
`http://localhost:5173` for Vite dev.

---

## 1. Domain shapes

```ts
type ToolStatus = { ffmpeg: string|null; ffprobe: string|null; ytdlp: string|null;
                    cuda: boolean; whisper: boolean; tracker: boolean };

type NodePorts = { inputs: Record<string,string>; outputs: Record<string,string> };

type NodeType = { type: string; title: string; category: string; description: string;
                  inputs: Record<string,string>; outputs: Record<string,string>;
                  params_schema: object };

type CaptionStyle = { key: string; label: string; font: string; mode: string;
                      font_size: number; position: number };

type ProjectSummary = {
  id: string; created: string; modified: string;
  source: string|null; title: string|null;
  has_source: boolean; has_transcript: boolean; has_clips: boolean;
  clip_count: number; render_count: number;
  thumbnail: string|null;        // /media/<id>/source/... first-frame jpg if present
};

type Clip = {
  id: string; title: string|null; start: number; end: number; score: number|null;
  reason: string|null; hook: string|null; keywords: string[];
  reframe: string|null; caption_style: string|null; lut: string|null; music: string|null;
  title_text: string|null; enabled: boolean;
  exclude_ranges: [number,number][]; loop_ending: boolean|null;
};

type ClipList = { version: number; source: object; defaults: object; clips: Clip[] };

type Render = { clip_id: string; path: string; duration: number; title: string|null;
                reframe: string; camera: string; url: string };   // url = /media/...

type ProjectDetail = {
  summary: ProjectSummary;
  transcript: { language: string|null; duration: number; segments: {start:number;end:number;text:string}[];
                words: {start:number;end:number;word:string}[] } | null;
  events: { lufs: number|null; silences: [number,number][] } | null;
  scenes: { count: number; cuts: number[] } | null;
  clips: ClipList | null;
  renders: Render[];
  defaults: object;
};

type JobEvent = { type: string; node: string|null; pct: number|null; message: string;
                  level: "info"|"warn"|"error"; ts: number; cached?: boolean };

type Job = { id: string; project_id: string; stage: "analysis"|"render";
             status: "queued"|"running"|"done"|"error"|"cancelled";
             error: string|null; created: number; events: JobEvent[]; result: object|null };
```

## 2. REST endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | — | `{status, version, tools: ToolStatus}` |
| GET | `/api/nodes` | — | `NodeType[]` |
| GET | `/api/styles` | — | `CaptionStyle[]` |
| GET | `/api/assets` | — | `{luts: string[], music: string[], fonts: string[]}` |
| GET | `/api/settings` | — | settings object |
| PUT | `/api/settings` | settings object (partial) | settings object (persisted to `data/settings.json`) |
| GET | `/api/cookies` | — | `CookieStatus` (see §7) |
| POST | `/api/cookies` | `{content?: string, from_browser?: string, source?: string}` | `CookieStatus` |
| DELETE | `/api/cookies` | — | `CookieStatus` |
| POST | `/api/cookies/verify` | — | `{ok, message, detail, status}` |
| GET | `/api/projects` | — | `ProjectSummary[]` |
| POST | `/api/projects` | `{source, id?, cookies?}` | `ProjectSummary` |
| GET | `/api/projects/{id}` | — | `ProjectDetail` |
| DELETE | `/api/projects/{id}` | — | `{ok: true}` |
| GET | `/api/projects/{id}/graph` | `?stage=analysis\|render` | `{nodes, edges}` (React Flow shape) |
| GET | `/api/projects/{id}/text` | — | `{txt, srt, payload, prompt}` (contents, may be null) |
| PUT | `/api/projects/{id}/clips` | `ClipList` | `ClipList` (validated) |
| POST | `/api/projects/{id}/clips/import` | `{inline?: string, path?: string}` | `ClipList` |
| GET | `/api/projects/{id}/metadata` | — | `{metadata: object, markdown: string}` |
| POST | `/api/projects/{id}/jobs` | `{stage, options?}` | `Job` |
| GET | `/api/projects/{id}/jobs` | — | `Job[]` |
| GET | `/api/jobs/{job_id}` | — | `Job` |
| POST | `/api/jobs/{job_id}/cancel` | — | `Job` |
| GET | `/media/{project_id}/{path:path}` | — | file stream (Range supported) |

`options` for `stage: "render"`:
```json
{ "clips_path": null, "clips_inline": null, "caption_style": null, "reframe": "auto",
  "lut": null, "music": null, "platform": "shorts", "add_titles": true, "track": true }
```
`options` for `stage: "analysis"`:
```json
{ "n_clips": 8, "min_duration": 15, "max_duration": 60, "cookies": null }
```

`/media` must guard path traversal (resolve under `data/projects/<id>`).

## 3. WebSocket

`WS /ws/jobs/{job_id}` → on connect, replay `job.events`, then stream new events.
Server sends each `JobEvent` as JSON text. On terminal status send:
`{"type":"__status","status":"done|error|cancelled"}` then close.

## 4. Behaviour requirements

- Jobs run in a background thread; the engine is synchronous. Bridge engine
  `emit(**kw)` callbacks into appended `JobEvent`s and broadcast to WS subscribers.
- `analysis` stage: build `analysis_graph(project_id, source, ...)`, run, result = export outputs.
- `render` stage: build `render_graph(...)`, run, then also run metadata; result = `{renders, metadata_file}`.
- Create the project row when `POST /api/projects` (source may be a URL or local path).
- `/api/projects/{id}/graph` translates `Graph.to_dict()` into React Flow shape:
  `nodes: [{id, type, position:{x,y}, data:{label, title, category, params, inputs, outputs}}]`,
  `edges: [{id, source, target, sourceHandle: port, targetHandle: port, animated:false}]`.
  Use the `ui.x/ui.y` from `Graph.to_dict()` for position.
- Settings exposed are `app.config.Settings` fields (render.*, default_caption_style, etc.).

## 5. UI specification (clean, professional — no "AI slop")

Design language: neutral slate palette, single accent (indigo), generous whitespace,
Inter / system sans, 1px borders, subtle shadows, **no heavy gradients, no emoji
fluff, no glassmorphism**. Support light + dark (dark default). Use accessible
focus rings. Keep motion minimal (150ms fades).

Routes:
- **`/` Dashboard** — project cards (thumbnail, title, clip/render counts, modified),
  "New project" (source URL/path + optional id + cookies), delete.
- **`/p/:id` Workspace** — header with title, stage buttons, and tabs:
  1. **Pipeline** — `@xyflow/react` canvas rendering the real graph; custom node
     cards (category colour dot, title, ports); live per-node status
     (idle/running/done/cached/error) + a slim progress bar; "Run analysis" /
     "Run render" buttons; node click opens a side panel with params (read-only v1).
  2. **Transcript** — tabs for Transcript / Payload / Prompt / SRT with copy buttons;
     "Open payload + prompt" convenience; import-clips textarea (JSON or CSV) with
     validate + save.
  3. **Clips** — table of candidates: score bar, title, `start–end`, duration, hook,
     enabled toggle, edit-in-place. Bulk enable/disable, sort by score.
  4. **Editor** — per-clip: caption style (from `/api/styles`), reframe
     (auto/crop/blur/pad), LUT (from assets), music (from assets), title text,
     exclude ranges (add/remove), then "Render selected".
  5. **Renders** — responsive grid of `<video src=url controls>` with title,
     duration, camera mode, download link, and publish metadata (title, hashtags,
     filename) from `/api/projects/{id}/metadata`.
- **`/settings`** — encoder, crf, resolution, loudness target, default caption
  style, whisper model, device.

State: no heavy framework; React Query (TanStack Query) for REST + a small WS hook
for job progress. Every long action shows inline progress, never blocks the UI.

## 6. Non-goals (v1)
No auth, no cloud, no multi-user. Localhost single-user only.

## 7. Cookies (global, shared by every project)

`CookieStatus`:
```ts
type CookieStatus = {
  present: boolean; count: number; session_cookies: number; authenticated: boolean;
  updated: string | null; source: string | null;
  earliest_expiry: number | null; days_left: number | null;
  expired: boolean; expiring_soon: boolean; warnings: string[];
};
```
- Cookies are stored once at `data/cookies/cookies.txt` (Netscape format) and used by
  every project automatically. `POST /api/cookies` accepts a cookie-editor JSON export
  **or** a raw Netscape file in `content`, or a browser name in `from_browser`.
- `app.config.Settings` gains `use_cookies: bool` and `cookies_from_browser: string|null`.
- Ingest automatically falls back to a no-cookie download if the saved cookies fail,
  and emits a `warn` job event saying so.
- UI: see `docs/UI_GUIDELINES.md` §5 (status dot, import, verify, clear, warnings banner).

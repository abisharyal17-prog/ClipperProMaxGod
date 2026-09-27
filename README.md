# Clipper

Modular, node-graph video clipper for short-form video (YouTube Shorts / Instagram
Reels / TikTok). Everything runs locally; clip *selection* is delegated to an
external AI you paste a transcript into.

## Two ways to run it

**1. Local (everything in one process).** Build the SPA and launch the desktop
app â€” no token, no network:

```powershell
scripts\setup.ps1
uv sync --extra ml --extra desktop
python -m app.desktop
```

**2. Hosted UI + local engine.** Put the UI on Vercel and let each visitor run
the engine on their own machine. The page detects whether an engine is running;
if not, it shows a single PowerShell command to set one up, then pairs
automatically. See [docs/DEPLOY.md](docs/DEPLOY.md).

```powershell
irm https://raw.githubusercontent.com/abisharyal17-prog/ClipperProMaxGod/main/scripts/install.ps1 | iex
```

Video processing always happens on the machine running the engine (ffmpeg +
CUDA); the browser only drives it. The engine binds to `127.0.0.1` and every
`/api`/`/media` call needs a bearer token, which the launcher hands to the UI in
the URL fragment (`#token=â€¦`).

## Workflow

```
0. Set cookies once:  Settings -> Cookies (paste a JSON export or cookies.txt, then Verify).
   Cookies are global and shared by every project. If they are missing, the app
   refuses to process a URL and asks you to add them first.

1. Create a project (URL + project name) and run analysis:
      download -> transcribe (word-level) -> analyse audio/scenes
      -> transcript/transcript.txt            (plain, timestamped)
      -> transcript/payload.txt               (enriched: [SIL]/[CUT] markers + loudness)
      -> transcript/prompt.txt                (strict instruction + JSON contract)
      -> transcript/prompt_and_transcript.txt (prompt + transcript in ONE paste)

2. Paste prompt_and_transcript.txt into any capable AI. It replies with JSON only.

3. Paste that JSON back into the app (Clips -> Import) and click Render.
      import -> refine bounds -> captions -> track face -> render 9:16 -> metadata
```

The prompt is model-agnostic and opinionated: it states the objective, what makes a
great clip, hard boundary rules, a scoring rubric, and an exact JSON output contract
with a worked example â€” so the AI returns importable JSON on the first try.

## Architecture â€” the graph is the app

Every stage is a **node** with typed input/output ports, and a **graph** wires
nodes together by port. The engine in `app/core/graph.py` executes nodes in
dependency order and caches each node's outputs. The *same* graph serializes to
JSON (`Graph.to_dict()`, `clipper graph <stage>`), and that JSON is exactly what
the web UI canvas renders and edits â€” **what you see is what runs.** There is no
separate "UI pipeline" that can drift from the real one.

```
app/core      DAG engine: nodes, ports, cache, registry, ffmpeg, cuda
app/nodes     pipeline stages (ingest, audio, transcribe, clips, captions, track, render)
app/pipeline  ready-made graphs: analysis_graph() and render_graph()
app/api       FastAPI server exposing the graph runner (served to the SPA)
web           Vite + React node-canvas SPA, built to web/dist
assets/       fonts, luts, music, templates
bin/          ffmpeg, ffprobe, yt-dlp (project-local)
data/projects per-video working dirs + cache
```

### Analysis â†’ paste â†’ render

1. **Analysis graph** (`app/pipeline/definitions.py:analysis_graph`) runs
   `ingest â†’ probe â†’ extract_audio â†’ analyze_audio / transcribe / detect_scenes â†’
   export_transcript`. It writes `payload.txt` (the transcript digest) and
   `prompt.txt` (instructions for your AI) into the project's `transcript/` dir.
2. You paste those into any AI and paste/point the returned JSON or CSV back in.
   `import_clips` accepts markdown-fenced JSON, bare arrays, single objects or CSV â€”
   see `_parse_payload` in `app/nodes/clips.py`.
3. **Render graph** (`render_graph`) runs `ingest â†’ transcribe â†’ import_clips â†’
   refine_bounds â†’ build_captions â†’ track_subject â†’ render_clips â†’
   export_metadata`. Outputs land in `data/projects/<id>/render/`.

### The clip contract

The AI only *has* to return `title`, `start`, `end`. Everything else is optional
and inherits project defaults. Times accept `HH:MM:SS.mmm`, `MM:SS`, or seconds.
See `app/schema.py`.

## Running

Setup once (self-contained toolchain into `bin/` + a project-local `.venv`):

```
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
uv sync                       # base deps
uv sync --extra ml            # + whisper / tracking (large download)
uv sync --extra desktop       # + pywebview (native window)
```

### CLI

```
.venv\Scripts\clipper.exe analyze "<url-or-file>" --n-clips 8
.venv\Scripts\clipper.exe render  "<url-or-file>" --clips clips.json ^
    --style hormozi --reframe auto --lut teal-orange --music lofi --platform shorts
.venv\Scripts\clipper.exe styles        # caption presets
.venv\Scripts\clipper.exe nodes         # node palette
.venv\Scripts\clipper.exe graph render --source "<url>"
```

`render` options: `--style` (see `styles`), `--reframe auto|crop|blur|pad`,
`--lut` (name from `assets/luts` or a path), `--music` (name from `assets/music`
or a path), `--platform shorts|reels|tiktok` (caption safe area),
`--titles/--no-titles`, `--track/--no-track`.

(Or `python -m app.cli ...` from the repo root.)

### Web

Build the SPA, then serve the API (which serves `web/dist`):

```
powershell -ExecutionPolicy Bypass -File scripts/build_web.ps1
.venv\Scripts\python.exe -m app.api.server      # http://127.0.0.1:8765
```

### Desktop

A native `pywebview` window around the same API:

```
powershell -ExecutionPolicy Bypass -File scripts/run.ps1            # native window
powershell -ExecutionPolicy Bypass -File scripts/run.ps1 -Browser   # browser instead
.venv\Scripts\python.exe -m app.desktop
```

`scripts/run.ps1` builds `web/dist` if it is missing, then launches
`app.desktop` (falling back to `app.api.server`). `scripts/doctor.ps1` prints a
health check of Python, ffmpeg, yt-dlp, torch/CUDA, faster-whisper, ultralytics,
fonts, LUTs and the built UI.

## Cookies (global, shared by every project)

Cookies are set **once** and used automatically by every project.

- **Settings â†’ Cookies** (web/desktop): paste a cookie-editor JSON export *or* a raw
  `cookies.txt`, or pick a browser profile. Stored at `data/cookies/cookies.txt`
  (gitignored â€” never commit it).
- **Verify** runs a live yt-dlp metadata fetch with the cookies. The UI shows a status
  dot and warns when cookies are expired, expiring within 7 days, or unauthenticated.
- If a download fails with the saved cookies, ingest **automatically retries without
  them** and emits a warning â€” public videos always work; gated/age-restricted ones need
  valid cookies.
- API: `GET/POST/DELETE /api/cookies`, `POST /api/cookies/verify`.

## Captions

Presets live in `app/config.py` (`CAPTION_PRESETS`) and each carries a `case` rule:
`upper` (Hormozi / Beast / Neon â€” high energy) or `sentence` (Karaoke / Dynamic Minimal
/ Clean â€” authority). Sentence case capitalises real sentence starts and the word "I".
`WrapStyle 0` is set so long lines **wrap inside the safe band** instead of overflowing,
and the block is clamped to the platform safe area (`--platform shorts|reels|tiktok`).

## Face tracking

`track_subject` uses OpenCV **YuNet** (a real face detector) with continuity bias so the
crop follows one speaker, falling back to the head region of the largest person box
(YOLO) when no face is found. The smoothed path is baked into a per-frame crop
expression, so the camera glides rather than jitters. `--reframe crop` keeps the face
centred; `blur`/`pad` letterbox instead.

## Colour grading

`scripts/generate_luts.py` builds ten license-free `.cube` grades from a shared filmic
pipeline (smoothstep contrast â†’ split-tone â†’ luma-preserving saturation â†’ highlight
roll-off): `cinematic`, `teal-orange`, `warm-film`, `cool-film`, `kodak`, `fuji`,
`fade`, `vibrant`, `noir`, `neutral`. Select with `--lut cinematic`.

## Assets

Everything the renderer reaches for lives under `assets/` and is resolved by name:

| Location        | Used for                        | Notes                                   |
| --------------- | ------------------------------- | --------------------------------------- |
| `assets/fonts`  | caption / title typefaces       | see `assets/fonts/README.md`            |
| `assets/luts`   | `.cube` colour grades           | see `assets/luts/README.md`             |
| `assets/music`  | ducked background beds          | see `assets/music/README.md`            |

## Caching

Execution is **content-addressed**. Before running a node the engine computes a
fingerprint over:

- the app version,
- the node type **and a hash of its source** (so editing a node invalidates it),
- its parameter values,
- the fingerprints of every upstream node feeding its input ports.

That hash keys a JSON artifact in `data/projects/<id>/cache/`. On the next run an
unchanged node is served from cache â€” no transcription, no re-encode â€” while any
changed param, wired input or node source busts the cache for that node and
everything downstream of it. This is why tuning one clip's caption style re-renders
in seconds instead of replaying the whole pipeline. To force a full rebuild, delete
the project's `cache/` directory.

## Tests

```
.venv\Scripts\python.exe -m pytest -q
```

Tests are offline: they exercise timecode parsing, the DAG cache, caption `.ass`
generation and ffmpeg command construction â€” no real ffmpeg/whisper/cuda needed.

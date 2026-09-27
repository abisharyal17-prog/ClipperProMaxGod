# Deploying Clipper (hosted UI + local engine)

Clipper runs video processing on **your own machine** (ffmpeg, CUDA, yt-dlp). A
browser tab can't do that â€” it can't spawn processes or use the GPU, and YouTube
blocks in-browser downloads. So the app is split in two:

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”        HTTP + WS        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  UI  (Vercel, static)    â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¶   â”‚  Engine (your PC:8765)     â”‚
â”‚  https://your.vercel.app â”‚  â—€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€   â”‚  FastAPI + ffmpeg + CUDA   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         ^                                                        ^
         â”‚ same one URL for everyone                             â”‚ installed once,
         â”‚ (always the latest UI)                                â”‚ per machine
```

- The **UI** is a static build (`web/dist`) hosted anywhere â€” Vercel works great.
- The **engine** is the Python backend. A visitor runs one command to install it
  on their own PC; it binds to `127.0.0.1:8765` and the hosted UI connects to it
  automatically.

This gets you the "open a link, use my own hardware, no manual setup" experience,
minus the one-time engine install (unavoidable â€” see *Why not pure web* below).

## How a visitor experiences it

1. They open `https://your.vercel.app`.
2. No engine yet â†’ the page shows a **single command** to paste into PowerShell.
3. They paste it. It downloads the app + toolchain + models, installs the Python
   deps, starts the engine, and **opens the UI already paired**.
4. The engine prints its address; the page lights up and is ready to clip.

## Why not pure web (no install at all)

- Browsers can't spawn `ffmpeg`/`yt-dlp` or use NVENC/CUDA.
- YouTube won't send CORS headers, so a browser can't fetch the video either.
- A WASM-only version would drop downloads, drop GPU encoding, and run 10â€“30Ã—
  slower â€” a different, much weaker product. Running a small local engine is the
  standard approach (Ollama, LM Studio, ComfyUI all do this).

## One-time setup (repo owner)

1. **Push this repo to GitHub.**
2. **Import it into Vercel.** `vercel.json` already sets the build
   (`npm --prefix web run build`, output `web/dist`) and the SPA rewrite.
3. **Set the build-time env vars** (Project â†’ Settings â†’ Environment Variables):

   | Variable               | Value                                                              |
   | ---------------------- | ------------------------------------------------------------------ |
   | `VITE_INSTALL_SCRIPT`  | `https://raw.githubusercontent.com/abisharyal17-prog/ClipperProMaxGod/main/scripts/install.ps1` |
   | `VITE_SETUP_DOCS` *(optional)* | link to your `docs/` or README                              |

   Do **not** set `VITE_API_BASE` for the hosted build â€” leaving it empty makes
   the UI target `http://127.0.0.1:8765`.
4. **Deploy.** The UI now shows the install command from `VITE_INSTALL_SCRIPT`.

The install command that users copy is:

```powershell
irm https://raw.githubusercontent.com/abisharyal17-prog/ClipperProMaxGod/main/scripts/install.ps1 | iex
```

From **cmd.exe** the equivalent is:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/abisharyal17-prog/ClipperProMaxGod/main/scripts/install.ps1 | iex"
```

## The engine

Install / start (idempotent â€” re-running just starts it):

```powershell
irm https://raw.githubusercontent.com/abisharyal17-prog/ClipperProMaxGod/main/scripts/install.ps1 | iex
```

What it places:

| Path                              | Contents                         |
| --------------------------------- | -------------------------------- |
| `%LOCALAPPDATA%\Clipper\repo`     | app source + `.venv` + `bin/`    |
| `%LOCALAPPDATA%\Clipper\repo\data`| projects, cookies, `auth.json`   |

Environment overrides:

| Variable                | Meaning                                            |
| ----------------------- | -------------------------------------------------- |
| `CLIPPER_HOST`          | bind address (default `127.0.0.1`)                 |
| `CLIPPER_PORT`          | port (default `8765`)                              |
| `CLIPPER_TOKEN`         | fixed token instead of the generated one           |
| `CLIPPER_AUTH=0`        | disable auth (development only)                    |
| `CLIPPER_ORIGINS`       | comma-separated allowed browser origins            |
| `CLIPPER_ORIGIN_REGEX`  | origin regex (defaults to `*.vercel.app` + loopback)|

## Security model

- **Loopback only.** The engine binds to `127.0.0.1`, so it isn't reachable from
  the network.
- **Bearer token.** Any web page the user visits could still *reach* loopback, so
  every `/api` and `/media` call needs a token. Hostile pages get `401`.
- **Fragment pairing.** The token is handed to the browser as a URL *fragment*
  (`https://app/#token=â€¦`), which is never sent to a server, then stored in
  `localStorage` and stripped from the address bar.
- `CLIPPER_AUTH=0` disables all of the above â€” **never** do that on a shared or
  tunneled machine.

If you expose the engine beyond loopback (a tunnel), also terminate TLS and keep
auth **on**.

## Data, sessions and portability

Each install is single-tenant — one engine, one person — so isolation is total:

- Cookies, projects, settings and the engine token live under
  `%LOCALAPPDATA%\Clipper\repo\data\` on that user's machine. The hosted UI is
  static and holds no data.
- **Job history is persisted** to `data/projects/<id>/jobs/*.json`, so it
  survives an engine restart. A job that was still running when the engine
  stopped is reloaded as `error` ("The engine restarted before this job
  finished.").
- **Export / import**: download a project as a portable `.zip` (the regenerable
  `cache/` is excluded) and import it on another machine. Archives are validated
  and rejected if they contain path-traversal entries.
- There are no accounts or logins anywhere in the stack.

The default CORS allow-list is loopback plus this project's own Vercel domains
(`clipper-promax-god*.vercel.app`). Pin it exactly with `CLIPPER_ORIGINS`, or
widen it with `CLIPPER_ORIGIN_REGEX`.

## Updating

- **UI:** push to `main`; Vercel redeploys. Users get it on next load.
- **Engine:** re-run the install command (or `-Update`); source and deps refresh.

## Local-only (no hosting)

You can skip all of the above:

```powershell
scripts\setup.ps1
uv sync --extra ml --extra desktop
python -m app.desktop
```

This serves the built UI from the same process and opens a native window; no
Vercel, no token needed (the desktop launcher pairs itself).

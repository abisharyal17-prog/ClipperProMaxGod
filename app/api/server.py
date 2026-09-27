"""FastAPI application serving the Clipper web API.

Run it with ``python -m app.api.server`` (or import and call :func:`main`). The
server binds to ``127.0.0.1:8765`` and, when ``web/dist`` exists, serves the built
frontend at ``/``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
from typing import Annotated, Any

import orjson
from fastapi import Body, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

import app.nodes  # noqa: F401  (ensures node types are registered)
from app import __version__, auth, paths, settings_store
from app import cookies as cookie_store
from app.api import jobs as job_registry
from app.api import projects
from app.api.middleware import AuthMiddleware, authorized
from app.api.schemas import (
    AssetList,
    CaptionStyle,
    ClipsImportRequest,
    CreateProjectRequest,
    GraphPayload,
    Job,
    JobCreateRequest,
    MetadataPayload,
    NodeType,
    ProjectDetail,
    ProjectSummary,
    TextPayload,
    ToolStatus,
)
from app.config import CAPTION_PRESETS, SETTINGS, Settings
from app.core import registry as node_registry
from app.pipeline.definitions import analysis_graph, render_graph
from app.schema import ClipList

# Apply any persisted settings (data/settings.json) before serving.
settings_store.load()

HOST = os.environ.get("CLIPPER_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLIPPER_PORT", "8765"))
DIST = paths.ROOT / "web" / "dist"

#: Exact browser origins allowed to call the engine (comma-separated env var).
DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
#: Regex fallback so a hosted UI works without pinning its deployment URL.
DEFAULT_ORIGIN_REGEX = (
    r"^https://([a-z0-9-]+\.)*vercel\.app$"
    r"|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("CLIPPER_ORIGINS")
    if raw is not None:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return list(DEFAULT_ORIGINS)


def _cors_origin_regex() -> str:
    return os.environ.get("CLIPPER_ORIGIN_REGEX", DEFAULT_ORIGIN_REGEX)



def _json_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class ORJSONResponse(Response):
    """orjson-backed JSON response (FastAPI now deprecates its own ORJSONResponse)."""

    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, default=_json_default)


app = FastAPI(
    title="Clipper",
    version=__version__,
    default_response_class=ORJSONResponse,
)


# --- health / catalog -----------------------------------------------------
def _probe_tool(fn: Any) -> str | None:
    try:
        return fn()
    except Exception:  # noqa: BLE001 - missing tool is a valid state
        return None


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


@app.get("/api/health", response_model=None)
def health() -> dict[str, Any]:
    tools = ToolStatus(
        ffmpeg=_probe_tool(paths.ffmpeg),
        ffprobe=_probe_tool(paths.ffprobe),
        ytdlp=_probe_tool(paths.ytdlp),
        cuda=_cuda_available(),
        whisper=_module_available("faster_whisper"),
        tracker=_module_available("ultralytics"),
    )
    return {
        "status": "ok",
        "name": "clipper-engine",
        "version": __version__,
        "auth_required": auth.auth_enabled(),
        "tools": tools.model_dump(),
    }


# --- auth (pairing) -------------------------------------------------------
@app.get("/api/auth/status")
def auth_status() -> dict[str, Any]:
    """Public: lets the UI tell 'engine missing' from 'engine needs a token'."""
    return auth.status()


@app.get("/api/auth/verify")
def auth_verify() -> dict[str, Any]:
    """Authenticated: confirms a presented token is valid."""
    return {"ok": True, "auth_required": auth.auth_enabled()}


@app.get("/api/nodes", response_model=list[NodeType])
def nodes() -> list[dict[str, Any]]:
    return node_registry.catalog()


@app.get("/api/styles", response_model=list[CaptionStyle])
def styles() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": preset.label,
            "font": preset.font,
            "mode": preset.mode,
            "case": preset.case,
            "font_size": preset.font_size,
            "position": preset.position,
            "highlight": preset.highlight,
        }
        for key, preset in CAPTION_PRESETS.items()
    ]


def _asset_names(folder: Path, suffixes: set[str] | None = None) -> list[str]:
    if not folder.is_dir():
        return []
    names: list[str] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if suffixes is not None and path.suffix.lower() not in suffixes:
            continue
        names.append(path.stem)
    return names


@app.get("/api/assets", response_model=AssetList)
def assets() -> dict[str, list[str]]:
    return {
        "luts": _asset_names(paths.LUTS_DIR, {".cube"}),
        "music": _asset_names(paths.MUSIC_DIR, {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}),
        "fonts": _asset_names(paths.FONTS_DIR, {".ttf", ".otf"}),
    }


# --- settings -------------------------------------------------------------
def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return SETTINGS.model_dump()


@app.put("/api/settings")
def put_settings(body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
    merged = _merge(SETTINGS.model_dump(), body)
    try:
        new = Settings(**merged)
    except Exception as exc:  # noqa: BLE001 - surface validation errors as 400
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for name in Settings.model_fields:
        setattr(SETTINGS, name, getattr(new, name))
    settings_store.save()
    return SETTINGS.model_dump()


# --- cookies (global, shared by every project) ----------------------------
@app.get("/api/cookies")
def get_cookies() -> dict[str, Any]:
    return cookie_store.status().to_dict()


@app.post("/api/cookies")
def import_cookies(body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
    from_browser = body.get("from_browser")
    content = body.get("content")
    if from_browser:
        SETTINGS.cookies_from_browser = str(from_browser)
        settings_store.save()
        return cookie_store.status().to_dict()
    if not content or not str(content).strip():
        raise HTTPException(status_code=400, detail="Provide 'content' or 'from_browser'")
    try:
        return cookie_store.import_text(str(content), source=str(body.get("source") or "paste")).to_dict()
    except cookie_store.CookieError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/cookies")
def delete_cookies() -> dict[str, Any]:
    return cookie_store.clear().to_dict()


@app.post("/api/cookies/verify")
def verify_cookies() -> dict[str, Any]:
    """Lightweight live check: can yt-dlp fetch metadata with these cookies?"""
    from app.core.proc import stream_command

    path = cookie_store.store_path()
    if not path:
        return {"ok": False, "message": "No cookie file to verify.", "detail": ""}
    url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    lines: list[str] = []
    code = stream_command(
        [paths.ytdlp(), "--cookies", str(path), "--simulate", "--skip-download",
         "--no-warnings", "--print", "%(id)s", url],
        on_line=lines.append,
        check=False,
        description="cookie verify",
    )
    ok = code == 0 and any(line.strip() == "jNQXAC9IVRw" for line in lines)
    detail = "\n".join(lines[-6:])
    message = "Cookies work." if ok else "yt-dlp could not use these cookies."
    return {"ok": ok, "message": message, "detail": detail, "status": cookie_store.status().to_dict()}


# --- projects -------------------------------------------------------------
def _default_title(source: str) -> str | None:
    if source.lower().startswith(("http://", "https://")):
        return None
    stem = Path(source).stem
    return stem or None


def _require_project(project_id: str) -> None:
    if not projects.exists(project_id):
        raise HTTPException(status_code=404, detail=f"project not found: {project_id}")


@app.get("/api/projects", response_model=list[ProjectSummary])
def list_projects() -> list[dict[str, Any]]:
    return projects.list_projects()


@app.post("/api/projects", response_model=ProjectSummary)
def create_project(body: CreateProjectRequest) -> dict[str, Any]:
    source = (body.source or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="source is required")
    from app.run import project_id_for

    project_id = project_id_for(source, body.id)
    projects.create_project(
        project_id, source, cookies=body.cookies, title=_default_title(source)
    )
    return projects.summary(project_id)


@app.get("/api/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str) -> dict[str, Any]:
    _require_project(project_id)
    return projects.detail(project_id)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, bool]:
    if not projects.delete_project(project_id):
        raise HTTPException(status_code=404, detail=f"project not found: {project_id}")
    return {"ok": True}


# --- graph / text / clips / metadata --------------------------------------
def graph_payload(project_id: str, stage: str) -> dict[str, Any]:
    source = projects.resolve_source(project_id)
    graph = render_graph(project_id, source) if stage == "render" else analysis_graph(
        project_id, source
    )
    raw = graph.to_dict()

    rf_nodes: list[dict[str, Any]] = []
    for node in raw["nodes"]:
        ui = node.get("ui") or {}
        rf_nodes.append(
            {
                "id": node["id"],
                "type": node["type"],
                "position": {"x": float(ui.get("x", 0)), "y": float(ui.get("y", 0))},
                "data": {
                    "label": node["title"],
                    "title": node["title"],
                    "category": node["category"],
                    "params": node["params"],
                    "inputs": node["inputs"],
                    "outputs": node["outputs"],
                },
            }
        )

    rf_edges: list[dict[str, Any]] = []
    for edge in raw["edges"]:
        src, dst = edge["from"], edge["to"]
        rf_edges.append(
            {
                "id": f"{src['node']}:{src['port']}->{dst['node']}:{dst['port']}",
                "source": src["node"],
                "target": dst["node"],
                "sourceHandle": src["port"],
                "targetHandle": dst["port"],
                "animated": False,
            }
        )
    return {"nodes": rf_nodes, "edges": rf_edges}


@app.get("/api/projects/{project_id}/graph", response_model=GraphPayload)
def project_graph(
    project_id: str, stage: str = Query("analysis")
) -> dict[str, Any]:
    _require_project(project_id)
    if stage not in {"analysis", "render"}:
        raise HTTPException(status_code=400, detail="stage must be 'analysis' or 'render'")
    return graph_payload(project_id, stage)


@app.get("/api/projects/{project_id}/text", response_model=TextPayload)
def project_text(project_id: str) -> dict[str, str | None]:
    _require_project(project_id)
    return projects.text_files(project_id)


@app.put("/api/projects/{project_id}/clips")
def put_clips(project_id: str, body: ClipList) -> dict[str, Any]:
    _require_project(project_id)
    try:
        return projects.save_clips(project_id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/clips/import")
def import_clips(project_id: str, body: ClipsImportRequest) -> dict[str, Any]:
    _require_project(project_id)
    try:
        return projects.import_clips(project_id, inline=body.inline, path=body.path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/metadata", response_model=MetadataPayload)
def project_metadata(project_id: str) -> dict[str, Any]:
    _require_project(project_id)
    return projects.metadata(project_id)


# --- jobs -----------------------------------------------------------------
def _project_source(project_id: str) -> str | None:
    import json as _json

    manifest = paths.PROJECTS / project_id / "project.json"
    if manifest.exists():
        try:
            return _json.loads(manifest.read_text(encoding="utf-8")).get("source")
        except (ValueError, OSError):
            return None
    return None


def _needs_download(project_id: str) -> bool:
    return not (paths.PROJECTS / project_id / "source" / "source.mp4").exists()


def _gate_cookies(project_id: str, stage: str) -> None:
    """Refuse to process a URL until cookies are configured and healthy."""
    if not getattr(SETTINGS, "require_cookies", True):
        return
    source = _project_source(project_id)
    is_url = bool(source) and str(source).lower().startswith(("http://", "https://"))
    if not is_url or not _needs_download(project_id):
        return
    if cookie_store.is_ready():
        return
    raise HTTPException(
        status_code=409,
        detail={
            "code": "cookies_required",
            "message": (
                "Add YouTube cookies in Settings before processing this URL. "
                "The video may be gated/age-restricted, or YouTube may require a signed-in session."
            ),
            "cookies": cookie_store.status().to_dict(),
        },
    )


@app.post("/api/projects/{project_id}/jobs", response_model=Job)
def create_job(project_id: str, body: JobCreateRequest) -> Job:
    _require_project(project_id)
    _gate_cookies(project_id, body.stage)
    return job_registry.REGISTRY.start(project_id, body.stage, body.options)


@app.get("/api/projects/{project_id}/jobs", response_model=list[Job])
def list_jobs(project_id: str) -> list[Job]:
    _require_project(project_id)
    return job_registry.REGISTRY.list_for_project(project_id)


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = job_registry.REGISTRY.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return job


@app.post("/api/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: str) -> Job:
    job = job_registry.REGISTRY.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return job


# --- media ----------------------------------------------------------------
@app.get("/media/{project_id}/{path:path}")
def media(project_id: str, path: str) -> FileResponse:
    target = projects.safe_media_path(project_id, path)
    if target is None or not target.is_file():
        raise HTTPException(status_code=404, detail="media not found")
    return FileResponse(target)


# --- websockets -----------------------------------------------------------
@app.websocket("/ws/jobs/{job_id}")
async def ws_jobs(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    if auth.auth_enabled() and not authorized(websocket.scope):
        await websocket.send_json({"type": "__status", "status": "unauthorized"})
        await websocket.close(code=1008)
        return
    loop = asyncio.get_running_loop()
    subscription = job_registry.REGISTRY.subscribe(job_id, loop)
    if subscription is None:
        await websocket.send_json({"type": "__status", "status": "error"})
        await websocket.close()
        return

    replayed, queue, terminal_status = subscription
    try:
        for event in replayed:
            await websocket.send_json(event)
        if terminal_status is not None:
            await websocket.send_json({"type": "__status", "status": terminal_status})
            return
        while True:
            item = await queue.get()  # type: ignore[union-attr]
            await websocket.send_json(item)
            if item.get("type") == "__status":
                return
    except WebSocketDisconnect:
        return
    finally:
        job_registry.REGISTRY.unsubscribe(job_id, queue)
        try:
            await websocket.close()
        except RuntimeError:
            pass


# --- middleware (added last == outermost; see app/api/middleware.py) ------
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)


# --- static frontend ------------------------------------------------------
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="web")


def pairing_url(base: str | None = None) -> str:
    """The URL a browser should open to pair with this engine (token in fragment)."""
    root = (base or f"http://{HOST}:{PORT}").rstrip("/")
    if not auth.auth_enabled():
        return root
    return f"{root}/#token={auth.ensure_token()}"


def main() -> None:
    """Entry point: run the API server (127.0.0.1:8765 by default)."""
    import uvicorn

    if auth.auth_enabled():
        token = auth.ensure_token()
        print("Clipper engine")
        print(f"  url:   http://{HOST}:{PORT}")
        print(f"  token: {token}")
        print(f"  open:  http://{HOST}:{PORT}/#token={token}")
    else:
        print("Clipper engine (auth disabled via CLIPPER_AUTH)")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


serve = main


if __name__ == "__main__":
    main()

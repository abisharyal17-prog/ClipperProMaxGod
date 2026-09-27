"""Project filesystem helpers.

Every read/write the API performs against ``data/projects/<id>`` goes through
here: the tiny per-project manifest, filesystem-derived summaries, aggregated
project detail, the transcript text files, clip import/validate and the
path-traversal-safe media resolver.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app import paths
from app.nodes.clips import _parse_payload
from app.nodes.metadata import ExportMetadataNode
from app.paths import PROJECTS, ProjectPaths
from app.run import build_context
from app.schema import ClipList

MANIFEST_NAME = "project.json"
EXPORTS_DIR = paths.DATA / "exports"
_CACHE_DIRNAME = "cache"
_VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi"}
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


# --- generic helpers ------------------------------------------------------
def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).isoformat()


def project_dir(project_id: str) -> Path:
    return PROJECTS / project_id


def exists(project_id: str) -> bool:
    return project_dir(project_id).is_dir()


def delete_project(project_id: str) -> bool:
    root = project_dir(project_id)
    if not root.is_dir():
        return False
    shutil.rmtree(root, ignore_errors=True)
    return not root.exists()


# --- manifest -------------------------------------------------------------
def manifest_path(project_id: str) -> Path:
    return project_dir(project_id) / MANIFEST_NAME


def read_manifest(project_id: str) -> dict[str, Any]:
    data = _load_json(manifest_path(project_id))
    return data if isinstance(data, dict) else {}


def write_manifest(project_id: str, data: dict[str, Any]) -> None:
    ProjectPaths(project_id).ensure()
    manifest_path(project_id).write_text(json.dumps(data, indent=2), encoding="utf-8")


def create_project(project_id: str, source: str, cookies: str | None = None,
                   title: str | None = None) -> dict[str, Any]:
    """Create the project directory tree and record its manifest."""
    ProjectPaths(project_id).ensure()
    existing = read_manifest(project_id)
    created = existing.get("created") or _iso(datetime.now().timestamp())
    manifest = {
        "id": project_id,
        "source": source,
        "title": title if title is not None else existing.get("title"),
        "created": created,
        "cookies": cookies if cookies is not None else existing.get("cookies"),
    }
    write_manifest(project_id, manifest)
    return manifest


# --- summaries / detail ---------------------------------------------------
def _has_source(project_id: str) -> bool:
    source_dir = project_dir(project_id) / "source"
    if (source_dir / "source.mp4").is_file():
        return True
    if source_dir.is_dir():
        return any(
            p.is_file() and p.suffix.lower() in _VIDEO_SUFFIXES for p in source_dir.iterdir()
        )
    return False


def _count(path: Path, key: str = "clips") -> int:
    data = _load_json(path)
    if isinstance(data, dict):
        items = data.get(key)
        if isinstance(items, list):
            return len(items)
    return 0


def _thumbnail(project_id: str) -> str | None:
    source_dir = project_dir(project_id) / "source"
    if not source_dir.is_dir():
        return None
    candidates = sorted(
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    )
    if not candidates:
        return None
    rel = f"source/{candidates[0].name}"
    return f"/media/{quote(project_id, safe='')}/{quote(rel, safe='/')}"


def summary(project_id: str) -> dict[str, Any]:
    """Compute a ProjectSummary from the filesystem (manifest + files)."""
    root = project_dir(project_id)
    manifest = read_manifest(project_id)
    source = manifest.get("source")
    title = manifest.get("title")
    if not title and isinstance(source, str) and source and not source.lower().startswith(
        ("http://", "https://")
    ):
        title = Path(source).stem or None

    stat = root.stat()
    created = manifest.get("created")
    if not isinstance(created, str) or not created:
        created = _iso(stat.st_ctime)

    return {
        "id": project_id,
        "created": created,
        "modified": _iso(stat.st_mtime),
        "source": source if isinstance(source, str) else None,
        "title": title if isinstance(title, str) else None,
        "has_source": _has_source(project_id),
        "has_transcript": (root / "transcript" / "transcript.json").is_file(),
        "has_clips": (root / "clips" / "clips.json").is_file(),
        "clip_count": _count(root / "clips" / "clips.json"),
        "render_count": _count(root / "render" / "render.json"),
        "thumbnail": _thumbnail(project_id),
    }


def list_projects() -> list[dict[str, Any]]:
    if not PROJECTS.is_dir():
        return []
    ids = [p.name for p in PROJECTS.iterdir() if p.is_dir()]
    summaries = [summary(pid) for pid in ids]
    summaries.sort(key=lambda item: item["modified"], reverse=True)
    return summaries


def resolve_source(project_id: str) -> str:
    """Return the pipeline source: manifest URL/path, else the local media file."""
    manifest = read_manifest(project_id)
    source = manifest.get("source")
    if isinstance(source, str) and source:
        return source
    source_dir = project_dir(project_id) / "source"
    if source_dir.is_dir():
        candidates = sorted(
            (p for p in source_dir.iterdir()
             if p.is_file() and p.suffix.lower() in _VIDEO_SUFFIXES),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
    return ""


def _render_url(project_id: str, item: dict[str, Any]) -> str:
    root = project_dir(project_id)
    clip_id = str(item.get("clip_id") or "")
    candidate = root / "render" / f"{clip_id}.mp4"
    if clip_id and candidate.is_file():
        return f"/media/{quote(project_id, safe='')}/render/{quote(clip_id, safe='')}.mp4"
    path = item.get("path")
    if isinstance(path, str) and path:
        try:
            rel = Path(path).resolve().relative_to(root.resolve())
            return f"/media/{quote(project_id, safe='')}/{quote(str(rel).replace(chr(92), '/'), safe='/')}"
        except (ValueError, OSError):
            pass
    return ""


def renders(project_id: str) -> list[dict[str, Any]]:
    data = _load_json(project_dir(project_id) / "render" / "render.json")
    items = data.get("clips") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "clip_id": item.get("clip_id", ""),
                "path": item.get("path", ""),
                "duration": float(item.get("duration") or 0.0),
                "title": item.get("title"),
                "reframe": item.get("reframe") or "auto",
                "camera": item.get("camera") or "static",
                "url": _render_url(project_id, item),
            }
        )
    return out


def detail(project_id: str) -> dict[str, Any]:
    """Aggregate a ProjectDetail from the on-disk artifacts."""
    root = project_dir(project_id)

    transcript = _load_json(root / "transcript" / "transcript.json")
    transcript_payload = None
    if isinstance(transcript, dict):
        transcript_payload = {
            "language": transcript.get("language"),
            "duration": float(transcript.get("duration") or 0.0),
            "segments": transcript.get("segments") or [],
            "words": transcript.get("words") or [],
        }

    events = _load_json(root / "events" / "audio.json")
    events_payload = None
    if isinstance(events, dict):
        events_payload = {
            "lufs": events.get("lufs"),
            "silences": events.get("silences") or [],
        }

    scenes = _load_json(root / "events" / "scenes.json")
    scenes_payload = None
    if isinstance(scenes, dict):
        scenes_payload = {
            "count": int(scenes.get("count") or 0),
            "cuts": scenes.get("cuts") or [],
        }

    clips_data = _load_json(root / "clips" / "clips.json")
    clips_payload = None
    defaults: dict[str, Any] = {}
    if isinstance(clips_data, dict):
        try:
            clip_list = ClipList.model_validate(clips_data)
            clips_payload = clip_list.model_dump()
            defaults = clips_payload.get("defaults", {})
        except ValueError:
            clips_payload = clips_data

    return {
        "summary": summary(project_id),
        "transcript": transcript_payload,
        "events": events_payload,
        "scenes": scenes_payload,
        "clips": clips_payload,
        "renders": renders(project_id),
        "defaults": defaults,
    }


def text_files(project_id: str) -> dict[str, str | None]:
    base = project_dir(project_id) / "transcript"
    return {
        "txt": _read_text(base / "transcript.txt"),
        "srt": _read_text(base / "transcript.srt"),
        "payload": _read_text(base / "payload.txt"),
        "prompt": _read_text(base / "prompt.txt"),
    }


def _read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


# --- clips ----------------------------------------------------------------
def save_clips(project_id: str, payload: Any) -> dict[str, Any]:
    """Validate a full ClipList and persist it as clips/clips.json."""
    clip_list = ClipList.model_validate(payload)
    out = project_dir(project_id) / "clips" / "clips.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(clip_list.model_dump(), indent=2), encoding="utf-8")
    return clip_list.model_dump()


def import_clips(project_id: str, inline: str | None = None,
                 path: str | None = None) -> dict[str, Any]:
    """Parse/repair a JSON or CSV payload (reusing the engine's parser) and save it."""
    raw = inline
    if not raw:
        if path:
            candidate = Path(path)
            if not candidate.is_file():
                raise FileNotFoundError(f"clip payload not found: {path}")
            raw = candidate.read_text(encoding="utf-8")
        else:
            default = project_dir(project_id) / "clips" / "clips.json"
            if not default.is_file():
                raise FileNotFoundError(
                    "No clip payload supplied; provide inline or path, "
                    "or place clips/clips.json in the project."
                )
            raw = default.read_text(encoding="utf-8")

    data = _parse_payload(raw)
    if not data.get("clips"):
        raise ValueError("Clip payload contains no clips")
    for index, clip in enumerate(data["clips"], start=1):
        if isinstance(clip, dict):
            clip.setdefault("id", f"clip_{index:03d}")
    return save_clips(project_id, data)


# --- metadata -------------------------------------------------------------
def metadata(project_id: str) -> dict[str, Any]:
    """Return ``{metadata, markdown}`` from disk, running the export node if needed."""
    render_dir = project_dir(project_id) / "render"
    json_path = render_dir / "metadata.json"
    md_path = render_dir / "metadata.md"

    if json_path.is_file() and md_path.is_file():
        return {
            "metadata": _load_json(json_path) or {},
            "markdown": _read_text(md_path) or "",
        }

    clips_data = _load_json(project_dir(project_id) / "clips" / "clips.json")
    if isinstance(clips_data, dict):
        try:
            clip_list = ClipList.model_validate(clips_data)
            ctx = build_context(project_id)
            node = ExportMetadataNode("metadata")
            node.run(
                ctx,
                {"clips": clip_list.model_dump(), "renders": renders(project_id)},
            )
        except (ValueError, OSError):
            pass

    return {
        "metadata": _load_json(json_path) or {},
        "markdown": _read_text(md_path) or "",
    }


# --- media ----------------------------------------------------------------
def safe_media_path(project_id: str, rel_path: str) -> Path | None:
    """Resolve ``rel_path`` under the project directory, rejecting traversal."""
    base = PROJECTS.resolve()
    root = (PROJECTS / project_id).resolve()
    if root != base and not root.is_relative_to(base):
        return None
    try:
        target = (root / rel_path).resolve()
    except (OSError, ValueError):
        return None
    if target != root and not target.is_relative_to(root):
        return None
    return target


# --- portability: export / import -----------------------------------------
def export_archive(project_id: str) -> Path:
    """Zip a project's artifacts to ``data/exports/<id>.zip`` (cache excluded)."""
    root = project_dir(project_id)
    if not root.is_dir():
        raise FileNotFoundError(f"project not found: {project_id}")

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_id) or "project"
    target = EXPORTS_DIR / f"{safe}.zip"
    tmp = target.with_suffix(".zip.tmp")

    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if rel.parts and rel.parts[0] == _CACHE_DIRNAME:
                continue  # regenerable, and can be huge
            archive.write(path, rel.as_posix())
    tmp.replace(target)
    return target


def _unique_project_id(preferred: str) -> str:
    base = "".join(c if c.isalnum() or c in "-_" else "_" for c in preferred).strip("_")
    base = base or "project"
    candidate = base
    index = 2
    while exists(candidate):
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def import_archive(zip_path: Path, project_id: str | None = None) -> str:
    """Extract a Clipper export into ``data/projects/<new-id>`` and return the id."""
    if not zip_path.is_file():
        raise FileNotFoundError(f"archive not found: {zip_path}")

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        # Tolerate an export wrapped in a single top-level directory.
        prefix = ""
        if "project.json" not in names:
            tops = {name.split("/", 1)[0] for name in names if "/" in name}
            if len(tops) == 1:
                prefix = next(iter(tops)) + "/"
        if f"{prefix}project.json" not in names:
            raise ValueError("not a Clipper project export (project.json missing)")

        manifest = json.loads(archive.read(f"{prefix}project.json").decode("utf-8"))
        preferred = project_id or str(manifest.get("id") or zip_path.stem)
        new_id = _unique_project_id(preferred)

        base = project_dir(new_id).resolve()
        base.mkdir(parents=True, exist_ok=True)
        for member in archive.infolist():
            if member.is_dir():
                continue
            rel = member.filename
            if prefix and rel.startswith(prefix):
                rel = rel[len(prefix):]
            if not rel:
                continue
            target = (base / rel).resolve()
            if target != base and not target.is_relative_to(base):
                raise ValueError(f"archive contains an unsafe path: {member.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(target, "wb") as out:
                shutil.copyfileobj(source, out)

    manifest["id"] = new_id
    write_manifest(new_id, manifest)
    return new_id

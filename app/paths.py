"""Filesystem layout and tool resolution.

Everything is project-local: binaries live in ``bin/``, assets in ``assets/``,
and per-video working data in ``data/projects/<id>/``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent
BIN: Path = ROOT / "bin"
ASSETS: Path = ROOT / "assets"
DATA: Path = ROOT / "data"
PROJECTS: Path = DATA / "projects"

FONTS_DIR: Path = ASSETS / "fonts"
LUTS_DIR: Path = ASSETS / "luts"
MUSIC_DIR: Path = ASSETS / "music"
TEMPLATES_DIR: Path = ASSETS / "templates"


def _resolve_tool(name: str, fallback: str) -> str:
    local = BIN / name
    if local.exists():
        return str(local)
    found = shutil.which(fallback)
    if found:
        return found
    raise FileNotFoundError(
        f"Cannot find '{name}'. Run scripts/setup.ps1 to install the toolchain into {BIN}."
    )


def ffmpeg() -> str:
    return _resolve_tool("ffmpeg.exe" if _is_windows() else "ffmpeg", "ffmpeg")


def ffprobe() -> str:
    return _resolve_tool("ffprobe.exe" if _is_windows() else "ffprobe", "ffprobe")


def ytdlp() -> str:
    return _resolve_tool("yt-dlp.exe" if _is_windows() else "yt-dlp", "yt-dlp")


def _is_windows() -> bool:
    import os

    return os.name == "nt"


class ProjectPaths:
    """Directory layout for one video project."""

    def __init__(self, project_id: str, base: Path | None = None) -> None:
        self.id = project_id
        self.root = (base or PROJECTS) / project_id

    # lazily created subdirectories
    @property
    def source(self) -> Path:
        return self._sub("source")

    @property
    def audio(self) -> Path:
        return self._sub("audio")

    @property
    def transcript(self) -> Path:
        return self._sub("transcript")

    @property
    def events(self) -> Path:
        return self._sub("events")

    @property
    def clips(self) -> Path:
        return self._sub("clips")

    @property
    def tracking(self) -> Path:
        return self._sub("tracking")

    @property
    def render(self) -> Path:
        return self._sub("render")

    @property
    def cache(self) -> Path:
        return self._sub("cache")

    def file(self, *parts: str) -> Path:
        p = self.root.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _sub(self, name: str) -> Path:
        p = self.root / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure(self) -> ProjectPaths:
        self.root.mkdir(parents=True, exist_ok=True)
        for part in ("source", "audio", "transcript", "events", "clips", "tracking", "render", "cache"):
            getattr(self, part)
        return self

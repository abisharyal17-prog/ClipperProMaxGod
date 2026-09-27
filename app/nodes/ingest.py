"""Input nodes: download/import media and probe its properties."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app import paths
from app.core.context import RunContext
from app.core.graph import Node
from app.core.proc import stream_command
from app.core.registry import register

_PCT = re.compile(r"\[download\]\s+([\d.]+)%")
_VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi"}


class IngestParams(BaseModel):
    source: str = ""
    cookies_from_browser: str | None = None
    cookies_file: str | None = None
    max_height: int = 1080


@register
class IngestNode(Node):
    type = "ingest"
    title = "Ingest"
    category = "input"
    description = "Download from a URL with yt-dlp, or import a local media file."
    outputs = {"media": "MediaFile", "info": "Json"}
    params_model = IngestParams

    def fingerprint(self, upstream: dict[str, str]) -> str:
        """Include the source file's size+mtime so edited/replaced inputs bust the cache."""
        signature = ""
        src = str(self.param("source", "")).strip()
        if src and not src.lower().startswith(("http://", "https://")):
            path = Path(src)
            if path.exists():
                st = path.stat()
                signature = f"{st.st_size}:{int(st.st_mtime)}"
        return super().fingerprint({**upstream, "__source__": signature})

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        src = str(self.param("source", "")).strip()
        if not src:
            raise ValueError("ingest.source is required (URL or local path)")
        ctx.project.ensure()

        if src.lower().startswith(("http://", "https://")):
            media = self._download(ctx, src)
        else:
            media = self._import(ctx, src)

        ctx.progress(1.0, "media ready")
        return {"media": str(media), "info": {"source": src, "filename": media.name}}

    def _download(self, ctx: RunContext, url: str) -> Path:
        max_h = self.param("max_height", 1080)
        template = str(ctx.project.source / "source.%(ext)s")
        options = [
            "--no-playlist",
            "--no-warnings",
            "-f",
            f"bv*[height<={max_h}]+ba/b[height<={max_h}]/b",
            "--merge-output-format",
            "mp4",
            "-o",
            template,
        ]
        cookie_args = self._cookie_args(ctx)

        def _line(line: str) -> None:
            m = _PCT.search(line)
            if m:
                ctx.progress(float(m.group(1)) / 100.0, "downloading")

        ctx.log(
            f"Downloading {url}" + (" (with cookies)" if cookie_args else "")
        )
        cmd = [paths.ytdlp(), *cookie_args, *options, url]
        try:
            stream_command(cmd, on_line=_line, description="yt-dlp")
        except RuntimeError:
            if not cookie_args:
                raise
            # Stale/broken cookies shouldn't block public downloads.
            ctx.log(
                "Download failed with the saved cookies; retrying without them "
                "(re-import fresh cookies in Settings if this content needs sign-in).",
                level="warn",
            )
            stream_command(
                [paths.ytdlp(), *options, url], on_line=_line, description="yt-dlp"
            )

        candidates = [
            p for p in ctx.project.source.glob("source.*") if p.suffix.lower() in _VIDEO_EXT
        ]
        if not candidates:
            raise RuntimeError("yt-dlp produced no media file")
        return max(candidates, key=lambda p: p.stat().st_mtime)

    def _cookie_args(self, ctx: RunContext) -> list[str]:
        """Prefer the global cookie store; fall back to a browser profile."""
        from app import cookies as cookie_store

        cookie_file = self.param("cookies_file")
        if not cookie_file and getattr(ctx.settings, "use_cookies", True):
            store = cookie_store.store_path()
            cookie_file = str(store) if store else None
        if cookie_file:
            return ["--cookies", cookie_file]
        browser = self.param("cookies_from_browser") or getattr(
            ctx.settings, "cookies_from_browser", None
        )
        if browser:
            return ["--cookies-from-browser", browser]
        return []

    def _import(self, ctx: RunContext, src: str) -> Path:
        origin = Path(src)
        if not origin.exists():
            raise FileNotFoundError(f"media not found: {src}")
        target = ctx.project.source / f"source{origin.suffix.lower()}"
        if origin.resolve() != target.resolve():
            ctx.log(f"Importing {origin.name}")
            shutil.copy2(origin, target)
        return target


def _parse_fps(value: str | None) -> float:
    if not value:
        return 0.0
    if "/" in value:
        num, _, den = value.partition("/")
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else 0.0
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


@register
class ProbeNode(Node):
    type = "probe"
    title = "Probe"
    category = "input"
    description = "Read duration, resolution, fps and audio presence."
    inputs = {"media": "MediaFile"}
    outputs = {"meta": "Json", "duration": "Seconds"}

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        media = inputs.get("media")
        if not media:
            raise ValueError("probe requires a media input")
        info = ctx.ffmpeg.probe(media)
        streams = info.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = float(info.get("format", {}).get("duration") or 0.0)
        fps = _parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        meta = {
            "duration": duration,
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "fps": round(fps, 3),
            "has_audio": audio is not None,
            "vcodec": video.get("codec_name"),
            "acodec": audio.get("codec_name") if audio else None,
        }
        ctx.log(f"{meta['width']}x{meta['height']} @ {meta['fps']}fps, {duration:.1f}s")
        return {"meta": meta, "duration": duration}

"""Thin, typed ffmpeg / ffprobe wrapper."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from app import paths
from app.core.proc import stream_command

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class FFmpeg:
    def __init__(self, log: Callable[[str], None] | None = None) -> None:
        self._log = log or (lambda _m: None)

    # -- inspection ---------------------------------------------------------
    def probe(self, path: str | Path) -> dict[str, Any]:
        res = subprocess.run(
            [
                paths.ffprobe(),
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
        )
        return json.loads(res.stdout or "{}")

    def duration(self, path: str | Path) -> float:
        info = self.probe(path)
        try:
            return float(info["format"]["duration"])
        except (KeyError, TypeError, ValueError):
            return 0.0

    def has_audio(self, path: str | Path) -> bool:
        return any(s.get("codec_type") == "audio" for s in self.probe(path).get("streams", []))

    def video_size(self, path: str | Path) -> tuple[int, int]:
        for s in self.probe(path).get("streams", []):
            if s.get("codec_type") == "video":
                return int(s.get("width", 0)), int(s.get("height", 0))
        return 0, 0

    # -- execution ----------------------------------------------------------
    def run(
        self,
        args: Sequence[str],
        *,
        duration: float | None = None,
        on_progress: Callable[[float], None] | None = None,
        description: str = "ffmpeg",
    ) -> None:
        cmd = [paths.ffmpeg(), "-hide_banner", "-nostdin", "-y", *args]
        stream_command(
            cmd,
            on_line=self._log if self._log else None,
            on_progress=on_progress,
            duration=duration,
            description=description,
        )

    def run_capture(self, args: Sequence[str], *, description: str = "ffmpeg") -> str:
        """Run ffmpeg, returning combined stdout+stderr (for measurement passes)."""
        res = subprocess.run(
            [paths.ffmpeg(), "-hide_banner", "-nostdin", "-y", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
        )
        if res.returncode != 0:
            raise RuntimeError(f"{description} failed:\n{res.stderr[-2000:]}")
        return (res.stdout or "") + (res.stderr or "")

    def measure_loudness(
        self,
        inputs: Sequence[str],
        audio_filter: str,
        output_args: Sequence[str],
    ) -> dict[str, float] | None:
        """Run a loudnorm measurement pass and return its parsed JSON."""
        args = list(inputs) + ["-filter_complex", audio_filter, "-map", "[aout]"]
        args += list(output_args) + ["-f", "null", "-"]
        text = self.run_capture(args, description="loudnorm measure")
        return parse_loudnorm(text)


def parse_loudnorm(text: str) -> dict[str, float] | None:
    import re

    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    out: dict[str, float] = {}
    for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
        try:
            value = float(data[key])
        except (KeyError, TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        out[key] = value
    return out

"""Audio nodes: extract a Whisper-ready track and analyse loudness/silences.

The analysis output is what turns a raw transcript into an *enriched* transcript
for clip selection: it feeds silence markers, loudness and energy into the
payload you paste into the external AI.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from app.core.context import RunContext
from app.core.graph import Node
from app.core.proc import stream_command
from app.core.registry import register

_SIL_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SIL_END = re.compile(r"silence_end:\s*(-?[\d.]+)")
_LUFS = re.compile(r"I:\s*(-?[\d.]+)\s*LUFS")


class ExtractAudioParams(BaseModel):
    sample_rate: int = 16000
    mono: bool = True


@register
class ExtractAudioNode(Node):
    type = "extract_audio"
    title = "Extract Audio"
    category = "audio"
    description = "Produce a clean mono WAV for speech recognition."
    inputs = {"media": "MediaFile"}
    outputs = {"audio": "AudioFile"}
    params_model = ExtractAudioParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        media = inputs.get("media")
        if not media:
            raise ValueError("extract_audio requires a media input")
        out = ctx.project.audio / "speech.wav"
        sr = self.param("sample_rate", 16000)
        channels = 1 if self.param("mono", True) else 2
        ctx.ffmpeg.run(
            [
                "-i", str(media),
                "-vn",
                "-ac", str(channels),
                "-ar", str(sr),
                "-c:a", "pcm_s16le",
                str(out),
            ],
            description="extract audio",
        )
        ctx.progress(1.0, "audio extracted")
        return {"audio": str(out)}


class AnalyzeParams(BaseModel):
    silence_noise_db: float = -30.0
    silence_min_duration: float = 0.35


@register
class AnalyzeAudioNode(Node):
    type = "analyze_audio"
    title = "Analyze Audio"
    category = "audio"
    description = "Detect silences and measure integrated loudness (LUFS)."
    inputs = {"audio": "AudioFile", "duration": "Seconds"}
    outputs = {"events": "Json", "events_file": "File"}
    params_model = AnalyzeParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        audio = inputs.get("audio")
        if not audio:
            raise ValueError("analyze_audio requires an audio input")
        duration = float(inputs.get("duration") or 0.0)

        silences: list[list[float]] = []
        lufs: float | None = None
        current_start: float | None = None

        def _line(line: str) -> None:
            nonlocal lufs, current_start
            m = _SIL_START.search(line)
            if m:
                current_start = float(m.group(1))
            m = _SIL_END.search(line)
            if m and current_start is not None:
                silences.append([current_start, float(m.group(1))])
                current_start = None
            m = _LUFS.search(line)
            if m:
                lufs = float(m.group(1))

        noise = self.param("silence_noise_db", -30.0)
        min_dur = self.param("silence_min_duration", 0.35)
        filt = (
            f"silencedetect=noise={noise}dB:d={min_dur},ebur128=peak=true"
        )
        stream_command(
            [
                ctx.ffmpeg_path if hasattr(ctx, "ffmpeg_path") else _ffmpeg_bin(),
                "-hide_banner",
                "-nostdin",
                "-i", str(audio),
                "-af", filt,
                "-f", "null",
                "-",
            ],
            on_line=_line,
            check=False,
            description="analyze audio",
        )

        events = {"duration": duration, "lufs": lufs, "silences": silences}
        events_file = ctx.project.events / "audio.json"
        events_file.write_text(json.dumps(events, indent=2), encoding="utf-8")
        ctx.progress(1.0, f"{len(silences)} silences, {lufs if lufs is None else round(lufs,1)} LUFS")
        return {"events": events, "events_file": str(events_file)}


def _ffmpeg_bin() -> str:
    from app import paths

    return paths.ffmpeg()

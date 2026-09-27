"""Speech recognition with word-level timestamps (faster-whisper).

Word timing is what makes pro captions and precise cuts possible, so it is on by
default. Falls back to CPU automatically if CUDA is unavailable.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.core.context import RunContext
from app.core.graph import Node
from app.core.registry import register


class TranscribeParams(BaseModel):
    model: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    language: str | None = None
    word_timestamps: bool = True
    vad_filter: bool = True
    beam_size: int = 5


@register
class TranscribeNode(Node):
    type = "transcribe"
    title = "Transcribe"
    category = "speech"
    description = "faster-whisper transcription with word-level timestamps."
    inputs = {"audio": "AudioFile"}
    outputs = {"transcript": "Transcript", "transcript_file": "File"}
    params_model = TranscribeParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        audio = inputs.get("audio")
        if not audio:
            raise ValueError("transcribe requires an audio input")

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "faster-whisper is not installed. Run: uv sync --extra ml"
            ) from exc

        device = self.param("device", "cuda")
        compute_type = self.param("compute_type", "float16")

        def _load(dev: str, ct: str):
            return WhisperModel(self.param("model", "large-v3"), device=dev, compute_type=ct)

        try:
            model = _load(device, compute_type)
        except Exception as exc:  # noqa: BLE001 - fall back to CPU
            ctx.log(f"CUDA load failed ({exc}); falling back to CPU int8", level="warn")
            device, compute_type = "cpu", "int8"
            model = _load(device, compute_type)

        ctx.progress(0.02, "transcribing")
        segments, info = model.transcribe(
            str(audio),
            language=self.param("language"),
            word_timestamps=self.param("word_timestamps", True),
            vad_filter=self.param("vad_filter", True),
            beam_size=self.param("beam_size", 5),
        )

        total = float(getattr(info, "duration", 0.0) or 0.0)
        seg_list: list[dict[str, Any]] = []
        words: list[dict[str, Any]] = []
        for seg in segments:
            seg_list.append(
                {
                    "id": len(seg_list),
                    "start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text": seg.text.strip(),
                }
            )
            for w in seg.words or []:
                words.append(
                    {
                        "start": round(float(w.start), 3),
                        "end": round(float(w.end), 3),
                        "word": w.word,
                        "prob": round(float(getattr(w, "probability", 0.0) or 0.0), 3),
                    }
                )
            if total:
                ctx.progress(min(0.99, float(seg.end) / total), f"{seg.end:.0f}/{total:.0f}s")

        transcript = {
            "language": getattr(info, "language", None),
            "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 3),
            "duration": total,
            "device": device,
            "model": self.param("model", "large-v3"),
            "segments": seg_list,
            "words": words,
        }
        out = ctx.project.transcript / "transcript.json"
        out.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        ctx.progress(1.0, f"{len(seg_list)} segments, {len(words)} words, lang={transcript['language']}")
        return {"transcript": transcript, "transcript_file": str(out)}


class LoadTranscriptParams(BaseModel):
    path: str | None = None


@register
class LoadTranscriptNode(Node):
    type = "load_transcript"
    title = "Load Transcript"
    category = "speech"
    description = "Load an existing transcript.json (skip re-transcribing / use hand edits)."
    outputs = {"transcript": "Transcript", "transcript_file": "File"}
    params_model = LoadTranscriptParams

    def fingerprint(self, upstream: dict[str, str]) -> str:
        """Include the transcript file's size+mtime so edits bust the cache."""
        from pathlib import Path

        path = self.param("path") or ""
        signature = ""
        if path and Path(path).exists():
            st = Path(path).stat()
            signature = f"{st.st_size}:{int(st.st_mtime)}"
        return super().fingerprint({**upstream, "__transcript__": signature})

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path

        path = self.param("path") or str(ctx.project.transcript / "transcript.json")
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"no transcript at {path}")
        transcript = json.loads(p.read_text(encoding="utf-8"))
        ctx.progress(1.0, f"loaded {len(transcript.get('segments', []))} segments")
        return {"transcript": transcript, "transcript_file": str(p)}

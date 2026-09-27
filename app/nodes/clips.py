"""Clip import + boundary refinement.

This is the bridge between the external AI and rendering:
  * :class:`ImportClipsNode` parses whatever the AI returned (JSON or CSV, with
    or without markdown fences), validates it and normalizes it.
  * :class:`RefineBoundsNode` snaps cut points to word boundaries and trims
    leading/trailing silence so cuts land cleanly instead of mid-word.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from pydantic import BaseModel

from app.core.context import RunContext
from app.core.graph import Node
from app.core.registry import register
from app.schema import ClipList, ClipSpec

_FENCE = re.compile(r"^```[a-zA-Z0-9]*\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE.sub("", text.strip())


def _slice_json(text: str) -> str:
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last != -1 and last > first:
        return text[first : last + 1]
    first, last = text.find("["), text.rfind("]")
    if first != -1 and last != -1 and last > first:
        return text[first : last + 1]
    return text


def _parse_payload(raw: str) -> dict[str, Any]:
    text = _strip_fences(raw)
    candidate = _slice_json(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return _parse_csv(text)
    if isinstance(data, list):
        return {"clips": data}
    if isinstance(data, dict) and "clips" not in data:
        # single clip object
        if "start" in data and "end" in data:
            return {"clips": [data]}
    if not isinstance(data, dict):
        raise ValueError("Clip payload must be a JSON object or array")
    return data


def _parse_csv(text: str) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(text))
    rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]
    if not rows:
        raise ValueError("Could not parse payload as JSON or CSV")
    clips = []
    for row in rows:
        clip: dict[str, Any] = {}
        for key, value in row.items():
            if key in ("", "none", "null") or value in ("", "null", "none"):
                continue
            if key in ("id", "title", "reason", "hook", "reframe", "caption_style",
                       "lut", "music", "title_text"):
                clip[key] = value
            elif key in ("start", "end"):
                clip[key] = value
            elif key == "score":
                try:
                    clip[key] = float(value)
                except ValueError:
                    pass
            elif key == "keywords":
                clip[key] = [k.strip() for k in value.split(";") if k.strip()]
        clips.append(clip)
    return {"clips": clips}


class ImportClipsParams(BaseModel):
    path: str | None = None
    inline: str | None = None


@register
class ImportClipsNode(Node):
    type = "import_clips"
    title = "Import Clips"
    category = "clips"
    description = "Validate and normalize the AI's clips.json / CSV into the canonical form."
    outputs = {"clips": "ClipList", "clips_file": "File", "count": "Int"}
    params_model = ImportClipsParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        raw = self.param("inline")
        if not raw:
            path = self.param("path")
            if not path:
                candidate = ctx.project.clips / "clips.json"
                if not candidate.exists():
                    raise ValueError(
                        "No clip payload supplied. Set import_clips.path or .inline, "
                        "or place an edited file at data/projects/<id>/clips/clips.json"
                    )
                raw = candidate.read_text(encoding="utf-8")
            else:
                raw = _read(path)

        data = _parse_payload(raw)
        if not data.get("clips"):
            raise ValueError("Clip payload contains no clips")

        for i, clip in enumerate(data["clips"], start=1):
            clip.setdefault("id", f"clip_{i:03d}")

        clip_list = ClipList.model_validate(data)

        # persist canonical form
        out = ctx.project.clips / "clips.json"
        out.write_text(
            json.dumps(clip_list.model_dump(), indent=2), encoding="utf-8"
        )
        ctx.progress(1.0, f"{len(clip_list.clips)} clips imported")
        return {
            "clips": clip_list.model_dump(),
            "clips_file": str(out),
            "count": len(clip_list.clips),
        }


def _read(path: str) -> str:
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"clip payload not found: {path}")
    return p.read_text(encoding="utf-8")


class RefineParams(BaseModel):
    snap_start_tolerance: float = 1.2
    snap_end_tolerance: float = 1.8
    trim_silence: bool = True
    min_duration: float = 5.0


@register
class RefineBoundsNode(Node):
    type = "refine_bounds"
    title = "Refine Bounds"
    category = "clips"
    description = "Snap cut points to word boundaries and trim boundary silence."
    inputs = {"clips": "ClipList", "transcript": "Transcript", "events": "Json"}
    outputs = {"clips": "ClipList", "clips_file": "File"}
    params_model = RefineParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        data = inputs.get("clips")
        if not data:
            raise ValueError("refine_bounds requires clips input")
        clip_list = ClipList.model_validate(data)
        transcript = inputs.get("transcript") or {}
        events = inputs.get("events") or {}

        words = transcript.get("words") or []
        starts = [float(w["start"]) for w in words]
        ends = [float(w["end"]) for w in words]
        silences = events.get("silences") or []
        min_dur = self.param("min_duration", 5.0)

        refined: list[ClipSpec] = []
        for clip in clip_list.clips:
            start, end = clip.start, clip.end

            if starts:
                cand = [s for s in starts if abs(s - start) <= self.param("snap_start_tolerance", 1.2)]
                if cand:
                    start = min(cand, key=lambda s: abs(s - start))
            if ends:
                cand = [e for e in ends if abs(e - end) <= self.param("snap_end_tolerance", 1.8)]
                if cand:
                    end = min(cand, key=lambda e: abs(e - end))

            if self.param("trim_silence", True):
                for sil in silences:
                    if sil[0] <= start <= sil[1] + 0.05:
                        start = min(sil[1], end - min_dur)
                    if sil[0] - 0.05 <= end <= sil[1]:
                        end = max(sil[0], start + min_dur)

            if end - start < min_dur:
                end = start + min_dur
            clip.start, clip.end = round(start, 3), round(end, 3)
            refined.append(clip)

        clip_list.clips = refined
        out = ctx.project.clips / "clips.json"
        out.write_text(json.dumps(clip_list.model_dump(), indent=2), encoding="utf-8")
        ctx.progress(1.0, f"{len(refined)} clips refined")
        return {"clips": clip_list.model_dump(), "clips_file": str(out)}

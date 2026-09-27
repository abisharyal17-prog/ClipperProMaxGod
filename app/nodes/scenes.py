"""Scene-cut detection (ffmpeg, no extra dependency).

Cut times let reframing switch at shot boundaries instead of mid-shot, and give
the clip-selection AI visual structure signals.
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

_PTS = re.compile(r"pts_time:([\d.]+)")


class SceneParams(BaseModel):
    threshold: float = 0.4


@register
class DetectScenesNode(Node):
    type = "detect_scenes"
    title = "Detect Scenes"
    category = "video"
    description = "Find shot boundaries via ffmpeg scene-change scoring."
    inputs = {"media": "MediaFile", "duration": "Seconds"}
    outputs = {"scenes": "Json", "scenes_file": "File"}
    params_model = SceneParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        media = inputs.get("media")
        if not media:
            raise ValueError("detect_scenes requires a media input")
        threshold = self.param("threshold", 0.4)
        cuts: list[float] = []

        def _line(line: str) -> None:
            m = _PTS.search(line)
            if m:
                cuts.append(round(float(m.group(1)), 3))

        from app import paths

        stream_command(
            [
                paths.ffmpeg(),
                "-hide_banner",
                "-nostdin",
                "-i", str(media),
                "-filter:v", f"select='gt(scene,{threshold})',showinfo",
                "-an",
                "-f", "null",
                "-",
            ],
            on_line=_line,
            check=False,
            description="scene detect",
        )
        unique = sorted(set(c for c in cuts if c > 0))
        scenes = {"count": len(unique), "cuts": unique}
        out = ctx.project.events / "scenes.json"
        out.write_text(json.dumps(scenes, indent=2), encoding="utf-8")
        ctx.progress(1.0, f"{len(unique)} scene cuts")
        return {"scenes": scenes, "scenes_file": str(out)}

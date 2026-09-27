"""Export per-clip publishing metadata (title, description, hashtags, filename)."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from app.core.context import RunContext
from app.core.graph import Node
from app.core.registry import register
from app.schema import ClipList


def _slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().lower())
    return re.sub(r"-+", "-", text).strip("-")[:48] or "clip"


class MetadataParams(BaseModel):
    base_hashtags: list[str] = ["shorts", "reels", "fyp", "viral"]
    platform: str = "shorts"
    max_hashtags: int = 12


@register
class ExportMetadataNode(Node):
    type = "export_metadata"
    title = "Export Metadata"
    category = "output"
    description = "Write titles, descriptions, hashtags and suggested filenames per clip."
    inputs = {"clips": "ClipList", "renders": "Json"}
    outputs = {"metadata": "Json", "metadata_file": "File"}
    params_model = MetadataParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        data = inputs.get("clips")
        if not data:
            raise ValueError("export_metadata requires clips input")
        renders = {r.get("clip_id"): r for r in (inputs.get("renders") or [])}
        clip_list = ClipList.model_validate(data)

        base = [h.lstrip("#") for h in self.param("base_hashtags", [])]
        entries = []
        for index, clip in enumerate(clip_list.enabled_clips(), start=1):
            keywords = [k.lstrip("#") for k in (clip.keywords or [])]
            tags = list(dict.fromkeys([*keywords, *base]))[: int(self.param("max_hashtags", 12))]
            title = (clip.title or f"Clip {index}").strip()
            description = clip.hook or clip.reason or title
            render = renders.get(clip.id, {})
            entries.append(
                {
                    "clip_id": clip.id,
                    "title": title,
                    "description": description,
                    "hashtags": [f"#{t}" for t in tags],
                    "filename": f"{index:02d}-{_slug(title)}.mp4",
                    "start": clip.start,
                    "end": clip.end,
                    "duration": round(clip.duration, 2),
                    "score": clip.score,
                    "path": render.get("path"),
                }
            )

        payload = {"platform": self.param("platform", "shorts"), "clips": entries}
        json_path = ctx.project.render / "metadata.json"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        md_lines = [f"# Publish pack ({payload['platform']})", ""]
        for e in entries:
            md_lines += [
                f"## {e['title']}",
                f"- file: `{e['filename']}`",
                f"- duration: {e['duration']}s" + (f"  score: {e['score']}" if e["score"] else ""),
                f"- description: {e['description']}",
                f"- hashtags: {' '.join(e['hashtags'])}",
                "",
            ]
        md_path = ctx.project.render / "metadata.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        ctx.progress(1.0, f"{len(entries)} metadata entries")
        return {"metadata": payload, "metadata_file": str(json_path)}

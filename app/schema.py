"""The clip contract — the schema the external AI returns and the app ingests.

The AI only *has* to provide ``title``, ``start`` and ``end``. Everything else is
optional and inherits from project defaults, so a minimal response already works.

Accepted time formats for ``start`` / ``end``:
    - seconds:            412.35
    - MM:SS               06:52
    - MM:SS.mmm           06:52.350
    - HH:MM:SS            01:06:52
    - HH:MM:SS.mmm        01:06:52.350
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

_TC_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2}(?:\.\d+)?)\s*$")


def parse_timecode(value: Any) -> float:
    """Normalize any accepted time representation to seconds (float)."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        raise ValueError(f"Unsupported time value: {value!r}")

    text = value.strip()
    # pure seconds
    try:
        return float(text)
    except ValueError:
        pass

    m = _TC_RE.match(text)
    if not m:
        raise ValueError(f"Unrecognized time format: {value!r}")
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2))
    seconds = float(m.group(3))
    return hours * 3600 + minutes * 60 + seconds


def format_timecode(seconds: float, millis: bool = True) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if millis:
        return f"{h:d}:{m:02d}:{s:06.3f}"
    return f"{h:d}:{m:02d}:{int(s):02d}"


class ClipSpec(BaseModel):
    """A single requested clip."""

    id: str
    title: str | None = None
    start: float
    end: float
    score: float | None = None
    reason: str | None = None
    hook: str | None = None
    keywords: list[str] = Field(default_factory=list)

    # per-clip overrides (None -> inherit project defaults)
    reframe: str | None = None
    caption_style: str | None = None
    lut: str | None = None
    music: str | None = None
    title_text: str | None = None

    # editing controls
    enabled: bool = True
    exclude_ranges: list[tuple[float, float]] = Field(default_factory=list)
    loop_ending: bool | None = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def _parse_time(cls, v: Any) -> float:
        return parse_timecode(v)

    @field_validator("exclude_ranges", mode="before")
    @classmethod
    def _parse_ranges(cls, v: Any) -> Any:
        if not v:
            return []
        out = []
        for item in v:
            if isinstance(item, dict):
                out.append((parse_timecode(item["start"]), parse_timecode(item["end"])))
            else:
                out.append((parse_timecode(item[0]), parse_timecode(item[1])))
        return out

    @model_validator(mode="after")
    def _check_range(self) -> ClipSpec:
        if self.end <= self.start:
            raise ValueError(f"clip {self.id}: end ({self.end}) must be after start ({self.start})")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


class ClipDefaults(BaseModel):
    aspect: str = "9:16"
    reframe: str = "auto"          # auto | crop | blur | split | pad
    caption_style: str = "dynamic-minimal"
    lut: str | None = None
    music: str | None = None
    title_text: str | None = None
    loop_ending: bool = False


class ClipList(BaseModel):
    """Top-level document the app ingests (and writes back after your edits)."""

    version: int = 1
    source: dict[str, Any] = Field(default_factory=dict)
    defaults: ClipDefaults = Field(default_factory=ClipDefaults)
    clips: list[ClipSpec]

    def enabled_clips(self) -> list[ClipSpec]:
        return [c for c in self.clips if c.enabled]

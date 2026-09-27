"""Pydantic request/response models for the web API.

Shapes mirror docs/WEBSPEC.md §1 so the TypeScript client and the Python server
stay in lock-step. Response models are intentionally permissive on nested
``object`` fields (transcript/events/scenes/clips) so we never reject a payload
the engine already produced.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# --- primitives -----------------------------------------------------------
class ToolStatus(BaseModel):
    ffmpeg: str | None = None
    ffprobe: str | None = None
    ytdlp: str | None = None
    cuda: bool = False
    whisper: bool = False
    tracker: bool = False


class NodeType(BaseModel):
    type: str
    title: str
    category: str
    description: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    params_schema: dict[str, Any] = Field(default_factory=dict)


class CaptionStyle(BaseModel):
    key: str
    label: str
    font: str
    mode: str
    case: str = "upper"
    font_size: int
    position: float
    highlight: str | None = None


class AssetList(BaseModel):
    luts: list[str] = Field(default_factory=list)
    music: list[str] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)


# --- domain shapes --------------------------------------------------------
class ProjectSummary(BaseModel):
    id: str
    created: str
    modified: str
    source: str | None = None
    title: str | None = None
    has_source: bool = False
    has_transcript: bool = False
    has_clips: bool = False
    clip_count: int = 0
    render_count: int = 0
    thumbnail: str | None = None


class Render(BaseModel):
    clip_id: str
    path: str
    duration: float = 0.0
    title: str | None = None
    reframe: str = "auto"
    camera: str = "static"
    url: str = ""


class ProjectDetail(BaseModel):
    summary: ProjectSummary
    transcript: dict[str, Any] | None = None
    events: dict[str, Any] | None = None
    scenes: dict[str, Any] | None = None
    clips: dict[str, Any] | None = None
    renders: list[Render] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)


class GraphNode(BaseModel):
    id: str
    type: str
    position: dict[str, float]
    data: dict[str, Any]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str
    targetHandle: str
    animated: bool = False


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class TextPayload(BaseModel):
    txt: str | None = None
    srt: str | None = None
    payload: str | None = None
    prompt: str | None = None


class MetadataPayload(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    markdown: str = ""


# --- jobs -----------------------------------------------------------------
JobStatus = Literal["queued", "running", "done", "error", "cancelled"]
JobStage = Literal["analysis", "render"]


class JobEvent(BaseModel):
    type: str
    node: str | None = None
    pct: float | None = None
    message: str = ""
    level: str = "info"
    ts: float
    cached: bool = False


class Job(BaseModel):
    id: str
    project_id: str
    stage: JobStage
    status: JobStatus = "queued"
    error: str | None = None
    created: float
    events: list[JobEvent] = Field(default_factory=list)
    result: dict[str, Any] | None = None


# --- requests -------------------------------------------------------------
class CreateProjectRequest(BaseModel):
    source: str
    id: str | None = None
    cookies: str | None = None


class ClipsImportRequest(BaseModel):
    inline: str | None = None
    path: str | None = None


class JobCreateRequest(BaseModel):
    stage: JobStage
    options: dict[str, Any] = Field(default_factory=dict)

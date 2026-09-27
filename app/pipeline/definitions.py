"""Pipeline builders: ready-made graphs for each stage of the workflow."""

from __future__ import annotations

import app.nodes  # noqa: F401  (registers node types)
from app.config import SETTINGS
from app.core import registry
from app.core.graph import Graph, Node


def _node(node_type: str, node_id: str, params: dict | None = None, wires: dict | None = None, ui: dict | None = None) -> Node:
    cls = registry.get_node(node_type)
    return cls(node_id, params=params, wires=wires or {}, ui=ui or {})


def analysis_graph(
    project_id: str,
    source: str,
    *,
    n_clips: int = 8,
    min_duration: int = 15,
    max_duration: int = 60,
    cookies_from_browser: str | None = None,
) -> Graph:
    """Ingest -> transcribe -> export the payload + prompt (no clips needed yet)."""
    nodes = [
        _node("ingest", "ingest", {"source": source, "cookies_from_browser": cookies_from_browser},
              ui={"x": 0, "y": 0}),
        _node("probe", "probe", wires={"media": {"node": "ingest", "port": "media"}},
              ui={"x": 260, "y": 0}),
        _node("extract_audio", "audio", wires={"media": {"node": "ingest", "port": "media"}},
              ui={"x": 260, "y": 180}),
        _node("analyze_audio", "analyze",
              wires={"audio": {"node": "audio", "port": "audio"},
                     "duration": {"node": "probe", "port": "duration"}},
              ui={"x": 520, "y": 180}),
        _node("transcribe", "transcribe", {
            "model": SETTINGS.whisper_model,
            "device": SETTINGS.transcribe_device,
            "compute_type": SETTINGS.whisper_compute_type,
            "language": SETTINGS.whisper_language,
        }, wires={"audio": {"node": "audio", "port": "audio"}}, ui={"x": 520, "y": 360}),
        _node("detect_scenes", "scenes",
              wires={"media": {"node": "ingest", "port": "media"},
                     "duration": {"node": "probe", "port": "duration"}},
              ui={"x": 520, "y": 0}),
        _node("export_transcript", "export", {
            "n_clips": n_clips, "min_duration": min_duration, "max_duration": max_duration,
        }, wires={
            "transcript": {"node": "transcribe", "port": "transcript"},
            "events": {"node": "analyze", "port": "events"},
            "scenes": {"node": "scenes", "port": "scenes"},
            "meta": {"node": "probe", "port": "meta"},
        }, ui={"x": 800, "y": 180}),
    ]
    return Graph(nodes, project_id=project_id)


def render_graph(
    project_id: str,
    source: str,
    *,
    clips_path: str | None = None,
    clips_inline: str | None = None,
    caption_style: str | None = None,
    reframe: str = "auto",
    lut: str | None = None,
    music: str | None = None,
    platform: str = "shorts",
    add_titles: bool = True,
    track_subjects: bool = True,
    cookies_from_browser: str | None = None,
) -> Graph:
    """Ingest -> transcribe -> import clips -> refine -> captions -> [track] -> render."""
    nodes = [
        _node("ingest", "ingest", {"source": source, "cookies_from_browser": cookies_from_browser},
              ui={"x": 0, "y": 0}),
        _node("probe", "probe", wires={"media": {"node": "ingest", "port": "media"}},
              ui={"x": 260, "y": 0}),
        _node("extract_audio", "audio", wires={"media": {"node": "ingest", "port": "media"}},
              ui={"x": 260, "y": 180}),
        _node("analyze_audio", "analyze",
              wires={"audio": {"node": "audio", "port": "audio"},
                     "duration": {"node": "probe", "port": "duration"}},
              ui={"x": 520, "y": 180}),
        _node("transcribe", "transcribe", {
            "model": SETTINGS.whisper_model,
            "device": SETTINGS.transcribe_device,
            "compute_type": SETTINGS.whisper_compute_type,
            "language": SETTINGS.whisper_language,
        }, wires={"audio": {"node": "audio", "port": "audio"}}, ui={"x": 520, "y": 360}),
        _node("import_clips", "import", {"path": clips_path, "inline": clips_inline},
              ui={"x": 520, "y": 0}),
        _node("refine_bounds", "refine",
              wires={"clips": {"node": "import", "port": "clips"},
                     "transcript": {"node": "transcribe", "port": "transcript"},
                     "events": {"node": "analyze", "port": "events"}},
              ui={"x": 800, "y": 0}),
        _node("build_captions", "captions",
              {"default_style": caption_style or SETTINGS.default_caption_style,
               "platform": platform, "add_titles": add_titles},
              wires={"clips": {"node": "refine", "port": "clips"},
                     "transcript": {"node": "transcribe", "port": "transcript"}},
              ui={"x": 1080, "y": 0}),
    ]

    tracks_wire = None
    if track_subjects:
        nodes.append(
            _node("track_subject", "track",
                  wires={"media": {"node": "ingest", "port": "media"},
                         "clips": {"node": "refine", "port": "clips"},
                         "meta": {"node": "probe", "port": "meta"}},
                  ui={"x": 800, "y": 220})
        )
        tracks_wire = {"node": "track", "port": "tracks"}

    render_wires = {
        "media": {"node": "ingest", "port": "media"},
        "clips": {"node": "refine", "port": "clips"},
        "ass_files": {"node": "captions", "port": "ass_files"},
        "meta": {"node": "probe", "port": "meta"},
    }
    if tracks_wire:
        render_wires["tracks"] = tracks_wire
    nodes.append(
        _node("render_clips", "render",
              {"default_reframe": reframe, "default_lut": lut, "default_music": music},
              wires=render_wires, ui={"x": 1360, "y": 0})
    )
    nodes.append(
        _node("export_metadata", "metadata",
              wires={"clips": {"node": "refine", "port": "clips"},
                     "renders": {"node": "render", "port": "renders"}},
              ui={"x": 1620, "y": 0})
    )
    return Graph(nodes, project_id=project_id)

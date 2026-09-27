"""Helpers to build a run context and execute a graph with callbacks."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from app.config import SETTINGS
from app.core.cache import Cache
from app.core.context import RunContext
from app.core.ffmpeg import FFmpeg
from app.core.graph import Graph
from app.paths import ProjectPaths


def project_id_for(source: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    import hashlib
    import re
    from pathlib import Path

    if source.lower().startswith(("http://", "https://")):
        return "yt_" + hashlib.md5(source.encode("utf-8")).hexdigest()[:8]
    return re.sub(r"[^A-Za-z0-9_-]", "_", Path(source).stem)[:40] or "project"


def build_context(
    project_id: str,
    emit: Callable[..., None] | None = None,
    cancel: threading.Event | None = None,
) -> RunContext:
    project = ProjectPaths(project_id).ensure()
    return RunContext(
        project=project,
        settings=SETTINGS,
        cache=Cache(project.cache),
        ffmpeg=FFmpeg(),
        emit=emit or (lambda **_k: None),
        cancel=cancel or threading.Event(),
    )


def run_graph(
    graph: Graph,
    project_id: str,
    emit: Callable[..., None] | None = None,
    cancel: threading.Event | None = None,
) -> tuple[dict[str, dict], RunContext]:
    ctx = build_context(project_id, emit=emit, cancel=cancel)
    results = graph.run(ctx)
    return results, ctx


def graph_to_dict(graph: Graph) -> dict[str, Any]:
    return graph.to_dict()

"""Execution context passed to every node."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from app.config import Settings
from app.core.cache import Cache
from app.core.ffmpeg import FFmpeg
from app.paths import ProjectPaths


class Cancelled(RuntimeError):
    """Raised when a run is cancelled."""


@dataclass
class RunContext:
    project: ProjectPaths
    settings: Settings
    cache: Cache
    ffmpeg: FFmpeg
    emit: Callable[..., None] = field(default=lambda **_k: None)
    cancel: threading.Event = field(default_factory=threading.Event)
    device: str = "cpu"
    current_node: str | None = None

    # -- events -------------------------------------------------------------
    def event(self, kind: str, **payload) -> None:
        self.emit(type=kind, node=self.current_node, **payload)

    def log(self, message: str, level: str = "info") -> None:
        self.event("log", message=message, level=level)

    def progress(self, pct: float, message: str = "") -> None:
        self.event("progress", pct=max(0.0, min(1.0, pct)), message=message)

    def child_progress(self, lo: float, hi: float) -> Callable[[float, str], None]:
        """Map a 0..1 sub-task onto the [lo, hi] slice of this node's progress."""
        span = hi - lo

        def _cb(fraction: float, message: str = "") -> None:
            self.progress(lo + span * max(0.0, min(1.0, fraction)), message)

        return _cb

    def check_cancel(self) -> None:
        if self.cancel.is_set():
            raise Cancelled("run cancelled")

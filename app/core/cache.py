"""Content-addressed artifact cache.

Each node's outputs are stored under ``<project>/cache/<key>.json`` where *key*
is a hash of the node type, its params and every upstream key. Re-running a
graph therefore skips unchanged work and re-renders a tweaked clip in seconds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def put(self, key: str, value: Any) -> None:
        self._path(key).write_text(
            json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8"
        )

    def clear(self) -> None:
        for p in self.root.glob("*.json"):
            p.unlink(missing_ok=True)

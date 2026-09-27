"""Persist app settings to ``data/settings.json`` and apply them at startup.

``app.config.SETTINGS`` is a module-level singleton that other modules import by
reference, so we mutate it in place rather than rebinding it.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app import paths
from app.config import SETTINGS

SETTINGS_FILE = paths.DATA / "settings.json"


def _apply(model: BaseModel, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if not hasattr(model, key):
            continue
        current = getattr(model, key)
        if isinstance(current, BaseModel) and isinstance(value, dict):
            _apply(current, value)
        else:
            try:
                setattr(model, key, value)
            except (ValueError, TypeError):
                continue


def load() -> None:
    if not SETTINGS_FILE.exists():
        return
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if isinstance(data, dict):
        _apply(SETTINGS, data)


def save() -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(SETTINGS.model_dump(), indent=2), encoding="utf-8"
    )


def update(patch: dict[str, Any]) -> None:
    _apply(SETTINGS, patch)
    save()

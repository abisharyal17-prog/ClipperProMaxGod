"""Shared pytest fixtures.

Tests never touch the real ``data/`` tree: every context points at a throwaway
project rooted in pytest's ``tmp_path``.
"""

from __future__ import annotations

import pytest

from app.config import SETTINGS
from app.core.cache import Cache
from app.core.context import RunContext
from app.core.ffmpeg import FFmpeg
from app.paths import ProjectPaths


@pytest.fixture
def ctx(tmp_path):
    """A RunContext bound to an isolated temp project (no real ffmpeg work)."""
    project = ProjectPaths("test_project", base=tmp_path).ensure()
    return RunContext(
        project=project,
        settings=SETTINGS,
        cache=Cache(project.cache),
        ffmpeg=FFmpeg(),
    )

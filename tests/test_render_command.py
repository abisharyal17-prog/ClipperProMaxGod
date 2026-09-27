"""ffmpeg command construction for the render node (no ffmpeg is executed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import RenderSettings
from app.nodes.render import RenderClipsNode


def _build(tmp_path: Path, reframe: str, plan: dict) -> list[str]:
    node = RenderClipsNode("render", {})
    return node._build(
        media="input.mp4",
        segments=[(0.0, 5.0)],
        reframe=reframe,
        lut=None,
        ass_path=None,
        settings=RenderSettings(),
        out_path=tmp_path / f"{reframe}.mp4",
        plan=plan,
        has_audio=True,
        loudness=None,
        duration=5.0,
        music=None,
    )


@pytest.mark.parametrize("reframe", ["crop", "blur", "pad"])
def test_build_contains_core_tokens(tmp_path, reframe):
    args = _build(tmp_path, reframe, {"mode": "static", "x": 0.0, "y": 0.0})

    assert "-filter_complex" in args
    assert "libx264" in args
    assert any("loudnorm" in token for token in args)


def test_crop_uses_crop_filter(tmp_path):
    args = _build(tmp_path, "crop", {"mode": "static", "x": 10.0, "y": 20.0})
    assert any("crop=" in token for token in args)


def test_dynamic_plan_emits_crop_expression(tmp_path):
    args = _build(
        tmp_path,
        "crop",
        {"mode": "dynamic", "x": 0.0, "y": 0.0,
         "xexpr": "if(lt(t,1.000),10.0,20.0)", "yexpr": "0.0"},
    )
    joined = " ".join(args)
    assert "crop=" in joined
    assert "x='if(" in joined


def test_trim_uses_clip_length_not_end_time(tmp_path):
    """Regression: -t must be the clip LENGTH (end - start), not the end timestamp."""
    node = RenderClipsNode("render", {})
    args = node._build(
        media="input.mp4",
        segments=[(10.0, 16.5)],
        reframe="crop",
        lut=None,
        ass_path=None,
        settings=RenderSettings(),
        out_path=tmp_path / "c.mp4",
        plan={"mode": "static", "x": 0.0, "y": 0.0},
        has_audio=True,
        loudness=None,
        duration=6.5,
        music=None,
    )
    start = args.index("-ss")
    assert args[start + 1] == "10.000"
    assert args[start + 3] == "6.500"
    assert "16.500" not in args

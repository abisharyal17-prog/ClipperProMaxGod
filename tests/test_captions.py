"""Caption construction: .ass output for a synthetic transcript + one clip."""

from __future__ import annotations

from pathlib import Path

from app.nodes.captions import BuildCaptionsNode
from app.schema import ClipList


def _synthetic_inputs() -> tuple[dict, dict]:
    words = [
        {"word": f"word{i}", "start": round(i * 0.4, 3), "end": round(i * 0.4 + 0.35, 3)}
        for i in range(30)
    ]
    transcript = {
        "words": words,
        "segments": [{"start": 0.0, "end": 12.0, "text": "hello world"}],
    }
    clips = ClipList.model_validate(
        {"clips": [{"id": "c1", "title": "My Big Title", "start": 0, "end": 12}]}
    )
    return clips.model_dump(), transcript


def _dialogue_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("Dialogue:")]


def test_generates_styled_ass_with_titles(ctx):
    clips, transcript = _synthetic_inputs()
    node = BuildCaptionsNode("cap", {"add_titles": True, "default_style": "dynamic-minimal"})

    out = node.run(ctx, {"clips": clips, "transcript": transcript})

    path = Path(out["ass_files"]["c1"])
    assert path.exists()
    text = path.read_text(encoding="utf-8")

    assert "Style: Default" in text
    assert "Style: Title" in text, "title style should exist when add_titles=True"
    assert len(_dialogue_lines(text)) > 3


def test_titles_can_be_disabled(ctx):
    clips, transcript = _synthetic_inputs()
    node = BuildCaptionsNode("cap", {"add_titles": False, "default_style": "dynamic-minimal"})

    out = node.run(ctx, {"clips": clips, "transcript": transcript})
    text = Path(out["ass_files"]["c1"]).read_text(encoding="utf-8")

    assert "Style: Default" in text
    assert "Style: Title" not in text
    assert len(_dialogue_lines(text)) > 3

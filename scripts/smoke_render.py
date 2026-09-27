"""End-to-end render smoke test (no ML required).

Creates a synthetic source video, a hand-made transcript and a clips payload,
then runs the real graph: ingest -> probe -> import -> refine -> captions -> render.
Verifies the ffmpeg filtergraph, ASS caption burn and loudness chain actually work.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.nodes  # noqa: E402,F401
from app.core import registry  # noqa: E402
from app.core.graph import Graph  # noqa: E402
from app.run import build_context  # noqa: E402

PROJECT = "smoke"
DURATION = 20.0


def _node(node_type, node_id, params=None, wires=None, ui=None):
    return registry.get_node(node_type)(node_id, params=params, wires=wires or {}, ui=ui or {})


def make_source(ctx) -> Path:
    out = ctx.project.source / "source.mp4"
    if out.exists():
        return out
    ctx.project.ensure()
    subprocess.run(
        [
            str(ROOT / "bin" / "ffmpeg.exe"), "-hide_banner", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30:duration={DURATION}",
            "-f", "lavfi", "-i", f"sine=frequency=320:duration={DURATION}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


def make_transcript(ctx) -> Path:
    words = []
    segments = []
    t = 1.0
    idx = 0
    while t < DURATION - 0.5:
        word = f"word{idx}"
        words.append({"start": round(t, 3), "end": round(t + 0.35, 3), "word": f" {word}", "prob": 0.9})
        if idx % 6 == 5:
            segments.append({
                "id": len(segments),
                "start": round(words[-6]["start"], 3),
                "end": round(t + 0.35, 3),
                "text": " ".join(w["word"].strip() for w in words[-6:]),
            })
        t += 0.4
        idx += 1
    transcript = {
        "language": "en", "duration": DURATION, "device": "synthetic", "model": "n/a",
        "segments": segments, "words": words,
    }
    path = ctx.project.transcript / "transcript.json"
    path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    return path


def main() -> int:
    def emit(**kw):
        kind = kw.get("type")
        if kind == "log":
            print("   ", kw.get("message"))
        elif kind in ("start", "done"):
            print(f"[{kind}]", kw.get("message"))

    ctx = build_context(PROJECT, emit=emit)
    make_source(ctx)
    transcript_path = make_transcript(ctx)

    clips_inline = json.dumps({
        "version": 1,
        "defaults": {"caption_style": "hormozi", "reframe": "crop"},
        "clips": [
            {"id": "clip_001", "title": "First moment", "start": "00:02.000", "end": "00:08.000",
             "score": 80, "caption_style": "hormozi"},
            {"id": "clip_002", "title": "Second moment", "start": "00:10.000", "end": "00:18.000",
             "score": 75, "caption_style": "karaoke", "reframe": "blur"},
        ],
    })

    nodes = [
        _node("ingest", "ingest", {"source": str(ctx.project.source / "source.mp4")}),
        _node("probe", "probe", wires={"media": {"node": "ingest", "port": "media"}}),
        _node("load_transcript", "load", {"path": str(transcript_path)}),
        _node("import_clips", "import", {"inline": clips_inline}),
        _node("refine_bounds", "refine", wires={
            "clips": {"node": "import", "port": "clips"},
            "transcript": {"node": "load", "port": "transcript"},
        }),
        _node("build_captions", "captions", wires={
            "clips": {"node": "refine", "port": "clips"},
            "transcript": {"node": "load", "port": "transcript"},
        }),
        _node("render_clips", "render", wires={
            "media": {"node": "ingest", "port": "media"},
            "clips": {"node": "refine", "port": "clips"},
            "ass_files": {"node": "captions", "port": "ass_files"},
            "meta": {"node": "probe", "port": "meta"},
        }),
    ]
    graph = Graph(nodes, project_id=PROJECT)

    print(f"graph order: {graph.order()}")
    results = graph.run(ctx)

    renders = results.get("render", {}).get("renders", [])
    print(f"\nrendered {len(renders)} clips")
    ok = True
    for item in renders:
        p = Path(item["path"])
        exists = p.exists() and p.stat().st_size > 1000
        ok = ok and exists
        w, h = ctx.ffmpeg.video_size(p) if exists else (0, 0)
        print(f"  {item['clip_id']}: exists={exists} size={p.stat().st_size if exists else 0} "
              f"{w}x{h} dur={item['duration']}")
    # caching check: second run should hit cache
    results2 = graph.run(ctx)
    print("\ncache re-run renders:", len(results2.get("render", {}).get("renders", [])))
    print("\nSMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

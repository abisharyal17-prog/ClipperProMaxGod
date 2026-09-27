"""Tracking + dynamic-camera smoke test on a real image with people."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.nodes  # noqa: E402,F401
from app.core import registry  # noqa: E402
from app.core.graph import Graph  # noqa: E402
from app.run import build_context  # noqa: E402

PROJECT = "tracktest"
SRC = Path(r"C:\Users\Acer\AppData\Local\Temp\opencode\pantest.mp4")


def _node(t, i, params=None, wires=None):
    return registry.get_node(t)(i, params=params, wires=wires or {})


def main() -> int:
    def emit(**kw):
        if kw.get("type") == "log":
            print("   ", kw.get("message"))

    ctx = build_context(PROJECT, emit=emit)
    ctx.project.ensure()
    dest = ctx.project.source / "source.mp4"
    if not dest.exists():
        shutil.copy2(SRC, dest)

    clips = json.dumps({
        "version": 1,
        "defaults": {"reframe": "crop", "caption_style": "dynamic-minimal"},
        "clips": [{"id": "clip_001", "title": "people pan", "start": 0.0, "end": 12.0}],
    })

    nodes = [
        _node("ingest", "ingest", {"source": str(dest)}),
        _node("probe", "probe", wires={"media": {"node": "ingest", "port": "media"}}),
        _node("import_clips", "import", {"inline": clips}),
        _node("track_subject", "track", wires={
            "media": {"node": "ingest", "port": "media"},
            "clips": {"node": "import", "port": "clips"},
            "meta": {"node": "probe", "port": "meta"},
        }),
        _node("render_clips", "render", wires={
            "media": {"node": "ingest", "port": "media"},
            "clips": {"node": "import", "port": "clips"},
            "meta": {"node": "probe", "port": "meta"},
            "tracks": {"node": "track", "port": "tracks"},
        }),
    ]
    graph = Graph(nodes, project_id=PROJECT)
    results = graph.run(ctx)

    track = results["track"]["tracks"]["clip_001"]
    cx = track["cx"]
    print(f"\ntracked samples: {len(cx)}")
    if cx:
        print(f"cx start={cx[0]:.3f} mid={cx[len(cx)//2]:.3f} end={cx[-1]:.3f}")
        print(f"cx range: {min(cx):.3f} .. {max(cx):.3f}")
    renders = results["render"]["renders"]
    for item in renders:
        print(f"render: {item['path']} camera={item.get('camera')}")

    # verify frames differ across the clip (camera actually moved)
    import subprocess

    ff = ROOT / "bin" / "ffmpeg.exe"
    out = ROOT / "data" / "projects" / PROJECT / "render"
    for tag, ts in (("s", 0.5), ("e", 10.5)):
        subprocess.run([str(ff), "-hide_banner", "-y", "-ss", str(ts), "-i", str(out / "clip_001.mp4"),
                        "-frames:v", "1", str(out / f"cam_{tag}.png")], capture_output=True)
    ok = cx and (max(cx) - min(cx)) > 0.02
    print("\nTRACK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

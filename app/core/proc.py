"""Generic subprocess helpers with live progress parsing.

Used by ffmpeg, yt-dlp and any other external tool. All output is streamed line
by line so the UI can show real progress instead of a frozen screen.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Sequence

_TIME_RE = re.compile(r"time=(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")


def _hidden_kwargs() -> dict:
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return kwargs


def stream_command(
    cmd: Sequence[str],
    *,
    on_line: Callable[[str], None] | None = None,
    on_progress: Callable[[float], None] | None = None,
    duration: float | None = None,
    cwd: str | None = None,
    check: bool = True,
    description: str = "",
) -> int:
    """Run *cmd*, streaming stderr/stdout lines.

    If *duration* (seconds) and *on_progress* are given, ffmpeg-style ``time=``
    markers are translated into a 0..1 progress fraction.
    """
    proc = subprocess.Popen(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **_hidden_kwargs(),
    )
    assert proc.stdout is not None
    tail: list[str] = []
    for raw in proc.stdout:
        line = raw.rstrip("\r\n")
        if line:
            tail.append(line)
            if len(tail) > 40:
                tail.pop(0)
            if on_line:
                on_line(line)
        if duration and on_progress:
            m = _TIME_RE.search(line)
            if m:
                seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                on_progress(min(1.0, seconds / duration))
    code = proc.wait()
    if check and code != 0:
        detail = "\n".join(tail[-25:])
        raise RuntimeError(
            f"{description or cmd[0]} failed with exit code {code}\n{detail}"
        )
    return code

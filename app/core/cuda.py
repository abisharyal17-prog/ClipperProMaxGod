"""Make pip-installed CUDA runtime DLLs (cuBLAS / cuDNN) discoverable on Windows.

ctranslate2 (used by faster-whisper) loads ``cublas64_12.dll`` and the cuDNN
DLLs at run time. The ``nvidia-*-cu12`` wheels ship them under
``site-packages/nvidia/<lib>/bin``, which is not on PATH by default. This must run
before the first model is created.
"""

from __future__ import annotations

import os
import sys

_registered = False


def register_cuda_dlls() -> list[str]:
    global _registered
    if _registered:
        return []
    _registered = True
    if sys.platform != "win32":
        return []

    try:
        import importlib.util

        spec = importlib.util.find_spec("nvidia")
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        return []

    from pathlib import Path

    roots = [Path(p) for p in (spec.submodule_search_locations or [])]
    dirs = [str(p) for root in roots for p in root.glob("*/bin") if p.is_dir()]
    if not dirs:
        return []

    os.environ["PATH"] = ";".join(dirs + [os.environ.get("PATH", "")])
    for d in dirs:
        try:
            os.add_dll_directory(d)  # type: ignore[attr-defined]
        except (OSError, AttributeError):
            pass
    return dirs

"""Clipper — modular node-graph video clipper for short-form video."""

import os
from pathlib import Path

__version__ = "0.1.0"

# Keep third-party caches inside the project so nothing leaks into the user profile.
_ROOT = Path(__file__).resolve().parent.parent
_ultra = _ROOT / ".ultralytics"
_ultra.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_ultra))

# Must happen before any CUDA-backed library (ctranslate2) is loaded. Imported
# lazily here to avoid a circular import with app.core.
from app.core.cuda import register_cuda_dlls as _register_cuda_dlls  # noqa: E402

_register_cuda_dlls()

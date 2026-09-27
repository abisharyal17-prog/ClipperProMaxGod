"""Generate self-contained, license-free .cube LUTs for the color stage.

Writing our own grades avoids any asset licensing questions and keeps the app
fully self-contained. Each grade is built from the same filmic pipeline:
smoothstep contrast -> split-toning -> luma-preserving saturation -> highlight
roll-off, so every look stays clean and never clips harshly.

Run: python scripts/generate_luts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "luts"
SIZE = 33


def _clamp(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 0.0, 1.0)


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def _contrast(rgb: np.ndarray, amount: float) -> np.ndarray:
    """Smoothstep S-curve blended by *amount* — gentle, film-like contrast."""
    s = rgb * rgb * (3.0 - 2.0 * rgb)
    return _clamp(rgb + (s - rgb) * amount)


def _saturation(rgb: np.ndarray, amount: float) -> np.ndarray:
    """Saturation that preserves luma (no brightness shift)."""
    lum = _luma(rgb)[..., None]
    return _clamp(lum + (rgb - lum) * amount)


def _split_tone(rgb: np.ndarray, shadow: tuple, highlight: tuple, strength: float = 1.0) -> np.ndarray:
    lum = _luma(rgb)[..., None]
    warm = _clamp((lum - 0.35) / 0.65)      # bright areas
    cool = _clamp((0.45 - lum) / 0.45)      # dark areas
    out = rgb + warm * np.array(highlight) * strength
    out = out + cool * np.array(shadow) * strength
    return _clamp(out)


def _rolloff(rgb: np.ndarray, knee: float = 0.72) -> np.ndarray:
    """Soft highlight compression so bright areas don't hard-clip."""
    low = np.minimum(rgb, knee)
    over = np.maximum(rgb - knee, 0.0)
    return _clamp(low + (1.0 - knee) * np.tanh(over / max(1e-6, 1.0 - knee)))


def _lift(rgb: np.ndarray, amount: float) -> np.ndarray:
    """Lift blacks (matte/faded look) while holding whites."""
    return _clamp(rgb * (1.0 - amount) + amount)


# --- grades ---------------------------------------------------------------
def grade_neutral(rgb):
    return rgb


def grade_cinematic(rgb):
    out = _contrast(rgb, 0.22)
    out = _split_tone(out, shadow=(-0.020, 0.005, 0.055), highlight=(0.055, 0.018, -0.035), strength=0.9)
    out = _saturation(out, 1.08)
    return _rolloff(out, 0.75)


def grade_teal_orange(rgb):
    out = _contrast(rgb, 0.30)
    out = _split_tone(out, shadow=(-0.045, 0.0, 0.085), highlight=(0.075, 0.020, -0.055), strength=1.0)
    out = _saturation(out, 1.14)
    return _rolloff(out, 0.74)


def grade_warm_film(rgb):
    out = rgb * np.array([1.06, 1.005, 0.94])
    out = _contrast(out, 0.20)
    out = _split_tone(out, shadow=(0.005, 0.0, 0.012), highlight=(0.05, 0.012, -0.01))
    out = _saturation(out, 1.06)
    return _rolloff(_lift(out, 0.015), 0.78)


def grade_cool_film(rgb):
    out = rgb * np.array([0.95, 1.0, 1.07])
    out = _contrast(out, 0.18)
    out = _split_tone(out, shadow=(-0.02, 0.0, 0.03), highlight=(0.0, 0.008, 0.03))
    out = _saturation(out, 1.04)
    return _rolloff(_lift(out, 0.015), 0.78)


def grade_kodak(rgb):
    out = _contrast(rgb, 0.24)
    out = out * np.array([1.04, 1.0, 0.95])
    out = _saturation(out, 1.18)
    return _rolloff(_lift(out, 0.02), 0.76)


def grade_fuji(rgb):
    out = _contrast(rgb, 0.18)
    out = out * np.array([0.99, 1.02, 1.01])
    out = _split_tone(out, shadow=(-0.012, 0.010, 0.006), highlight=(0.006, 0.012, 0.010))
    out = _saturation(out, 1.06)
    return _rolloff(_lift(out, 0.025), 0.80)


def grade_fade(rgb):
    out = _lift(rgb, 0.085)
    out = _contrast(out, 0.10)
    out = _saturation(out, 0.82)
    return _rolloff(out, 0.85)


def grade_vibrant(rgb):
    out = _saturation(rgb, 1.30)
    out = _contrast(out, 0.18)
    return _rolloff(out, 0.76)


def grade_noir(rgb):
    lum = _luma(rgb)[..., None]
    out = _contrast(lum, 0.32)
    return _clamp(np.repeat(out, 3, axis=-1))


GRADES = {
    "cinematic": grade_cinematic,
    "teal-orange": grade_teal_orange,
    "warm-film": grade_warm_film,
    "cool-film": grade_cool_film,
    "kodak": grade_kodak,
    "fuji": grade_fuji,
    "fade": grade_fade,
    "vibrant": grade_vibrant,
    "noir": grade_noir,
    "neutral": grade_neutral,
}


def build_grid(size: int) -> np.ndarray:
    vals = np.linspace(0.0, 1.0, size)
    # axes are (b, g, r) so r is the fastest-varying component when flattened
    b, g, r = np.meshgrid(vals, vals, vals, indexing="ij")
    return np.stack([r, g, b], axis=-1).astype(np.float64)


def write_cube(path: Path, title: str, size: int, fn) -> int:
    out = fn(build_grid(size))
    flat = out.reshape(-1, 3)
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in flat]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(flat)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.cube"):
        old.unlink()
    for name, fn in GRADES.items():
        path = OUT / f"{name}.cube"
        count = write_cube(path, name.replace("-", " ").title(), SIZE, fn)
        print(f"  + {path.name}  ({count} entries, {path.stat().st_size // 1024} KB)")
    print(f"\n{len(GRADES)} LUTs written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

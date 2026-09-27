"""Fetch the caption fonts (Google Fonts, SIL OFL / Apache — free commercial use).

Static weights are required: libass renders the default instance of a variable
font (i.e. too thin). Single-weight families come from google-webfonts-helper;
the variable families we need (Montserrat) are instanced locally with fontTools,
which keeps the family name correct so libass matches it.

Run: python scripts/fetch_fonts.py
"""

from __future__ import annotations

import io
import sys
import urllib.parse
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "fonts"
UA = {"User-Agent": "Mozilla/5.0"}

# (source, key, variant/named-name, output stem)
GWFH = [
    ("anton", "regular", "Anton-400"),
    ("archivo-black", "regular", "ArchivoBlack-400"),
    ("bebas-neue", "regular", "BebasNeue-400"),
    ("poppins", "700", "Poppins-700"),
    ("inter", "700", "Inter-700"),
    ("oswald", "600", "Oswald-600"),
    ("roboto", "900", "Roboto-900"),
    ("luckiest-guy", "regular", "LuckiestGuy-400"),
    ("bangers", "regular", "Bangers-400"),
]

VARIABLE = [
    ("ofl/montserrat/Montserrat[wght].ttf", {"wght": 900}, "Montserrat-900"),
]


def _gwfh(family: str, variant: str, client: httpx.Client) -> bytes:
    url = (
        f"https://gwfh.mranftl.com/api/fonts/{family}"
        f"?download=zip&subsets=latin&variants={variant}&formats=ttf"
    )
    resp = client.get(url, headers=UA, follow_redirects=True, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".ttf"))
        return zf.read(name)


def _variable(repo_path: str, axes: dict[str, float], client: httpx.Client) -> bytes:
    from fontTools import ttLib
    from fontTools.varLib import instancer

    quoted = urllib.parse.quote(repo_path)
    url = f"https://raw.githubusercontent.com/google/fonts/main/{quoted}"
    resp = client.get(url, headers=UA, follow_redirects=True, timeout=120)
    resp.raise_for_status()
    font = ttLib.TTFont(io.BytesIO(resp.content))
    instance = instancer.instantiateVariableFont(font, axes)
    buf = io.BytesIO()
    instance.save(buf)
    return buf.getvalue()


def _validate(data: bytes) -> tuple[str, str]:
    from PIL import ImageFont

    font = ImageFont.truetype(io.BytesIO(data), 24)
    return font.getname()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # clear anything previously downloaded
    for old in OUT.glob("*.ttf"):
        old.unlink()

    ok = 0
    with httpx.Client() as client:
        for family, variant, stem in GWFH:
            try:
                data = _gwfh(family, variant, client)
                (OUT / f"{stem}.ttf").write_bytes(data)
                fam, style = _validate(data)
                print(f"  + {stem:22} {fam} / {style}")
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {stem:22} {exc}")

        for repo_path, axes, stem in VARIABLE:
            try:
                data = _variable(repo_path, axes, client)
                (OUT / f"{stem}.ttf").write_bytes(data)
                fam, style = _validate(data)
                print(f"  + {stem:22} {fam} / {style}  (instanced)")
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {stem:22} {exc}")

    print(f"\n{ok} fonts written to {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

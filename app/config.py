"""App settings and the built-in caption style presets.

Preset geometry is expressed for a 1080x1920 canvas. Stroke widths, sizes and
positions follow the 2026 short-form conventions (see README for sources).
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CaptionStyle(BaseModel):
    """A complete, renderable caption look."""

    key: str
    label: str
    font: str
    font_size: int = 96           # px on a 1080-wide canvas
    bold: bool = True
    uppercase: bool = False       # legacy flag; prefer `case`
    case: str = "upper"           # upper | sentence | lower | title | as-is
    italic: bool = False

    fill: str = "#FFFFFF"
    highlight: str | None = "#FFD93D"   # active-word colour (karaoke/hormozi)
    mode: str = "word"            # word | phrase | karaoke | static

    stroke: str = "#000000"
    stroke_width: int = 9
    shadow: float = 2.0

    position: float = 0.64        # vertical centre of the caption block (0..1)
    max_words: int = 3            # words per on-screen beat
    margin_lr: int = 90
    line_spacing: float = 1.05

    animation: str = "pop"        # pop | fade | none
    pop_scale: float = 108.0      # percentage scale at pop peak

    box: bool = False             # pill / plate behind the text
    box_color: str = "#000000AA"
    box_padding: int = 18


# The looks clippers actually use in 2026. Keys are referenced by clips.json.
# `case`: "upper" = high-energy (Hormozi/Beast); "sentence" = authority/clean.
CAPTION_PRESETS: dict[str, CaptionStyle] = {
    "hormozi": CaptionStyle(
        key="hormozi", label="Hormozi / Bold Pop",
        font="Montserrat", font_size=104, case="upper",
        fill="#FFFFFF", highlight="#FFD93D", mode="word",
        stroke="#000000", stroke_width=11, position=0.64,
        max_words=2, animation="pop", pop_scale=110.0,
    ),
    "karaoke": CaptionStyle(
        key="karaoke", label="Karaoke Highlight",
        font="Montserrat", font_size=88, case="sentence",
        fill="#FFFFFF", highlight="#FFD93D", mode="karaoke",
        stroke="#000000", stroke_width=8, position=0.66,
        max_words=4, animation="none",
    ),
    "dynamic-minimal": CaptionStyle(
        key="dynamic-minimal", label="Dynamic Minimal",
        font="Inter", font_size=84, case="sentence", bold=True,
        fill="#FFFFFF", highlight=None, mode="phrase",
        stroke="#000000", stroke_width=4, shadow=3.0, position=0.68,
        max_words=4, animation="fade",
    ),
    "beast": CaptionStyle(
        key="beast", label="Beast / MrBeast",
        font="Anton", font_size=110, case="upper",
        fill="#FFFFFF", highlight=None, mode="word",
        stroke="#000000", stroke_width=12, position=0.62,
        max_words=3, animation="pop", pop_scale=112.0,
    ),
    "neon": CaptionStyle(
        key="neon", label="Neon Glow",
        font="Archivo Black", font_size=96, case="upper",
        fill="#39FF14", highlight="#00E5FF", mode="word",
        stroke="#001510", stroke_width=6, shadow=8.0, position=0.64,
        max_words=2, animation="fade",
    ),
    "clean": CaptionStyle(
        key="clean", label="Clean Minimal",
        font="Inter", font_size=64, case="sentence", bold=False,
        fill="#FFFFFF", highlight=None, mode="static",
        stroke="#000000", stroke_width=3, shadow=2.0, position=0.72,
        max_words=7, animation="none",
    ),
}

DEFAULT_CAPTION_STYLE = "dynamic-minimal"


class RenderSettings(BaseModel):
    """Encoding + canvas defaults."""

    width: int = 1080
    height: int = 1920
    fps: int = 0                  # 0 -> inherit source fps
    encoder: str = "libx264"      # libx264 | h264_nvenc
    crf: int = 18
    preset: str = "medium"
    audio_bitrate: str = "192k"
    audio_lufs: float = -14.0     # platform loudness target
    faststart: bool = True


class Settings(BaseSettings):
    """Top-level app settings.

    Override any field via environment variables, e.g.
    ``CLIPPER_WHISPER_MODEL=small`` or ``CLIPPER_RENDER__CRF=20``.
    """

    model_config = SettingsConfigDict(env_prefix="CLIPPER_", env_nested_delimiter="__")

    render: RenderSettings = Field(default_factory=RenderSettings)
    default_caption_style: str = DEFAULT_CAPTION_STYLE
    default_reframe: str = "auto"
    whisper_model: str = "large-v3"
    whisper_compute_type: str = "float16"
    whisper_language: str | None = None
    transcribe_device: str = "cuda"

    # cookies: a single global store shared by every project
    use_cookies: bool = True
    require_cookies: bool = True              # block URL processing until cookies are set
    cookies_from_browser: str | None = None   # fallback: yt-dlp --cookies-from-browser


SETTINGS = Settings()

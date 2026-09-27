"""Burn-in caption construction (ASS / libass).

Implements the researched short-form looks — word-by-word pop, karaoke highlight,
dynamic minimal, Beast, neon and clean — driven by
:data:`app.config.CAPTION_PRESETS`.

Captions are written clip-local (t=0 is the clip start) so the renderer can burn
them after trimming without retiming. Text wrapping is enabled and kept inside the
platform safe band so nothing overflows the frame or hides behind platform UI.
"""

from __future__ import annotations

import re
from typing import Any

import pysubs2
from pydantic import BaseModel

from app.config import CAPTION_PRESETS, DEFAULT_CAPTION_STYLE, CaptionStyle
from app.core.context import RunContext
from app.core.graph import Node
from app.core.registry import register
from app.schema import ClipList

# Vertical safe bands (top, bottom) as a fraction of frame height. The caption
# block centre is clamped inside these so it clears platform UI everywhere.
PLATFORM_SAFE = {
    "shorts": (0.08, 0.80),
    "reels": (0.10, 0.76),
    "tiktok": (0.10, 0.72),
}
UNIVERSAL_MAX_POSITION = 0.70  # cross-platform sweet spot (~55-70% from top)

_SENTENCE_END = re.compile(r"[.!?…]['\")\]]*$")
_I_CONTRACTIONS = {"i", "i'm", "i'll", "i've", "i'd"}


def _hex_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) == 8:
        v = v[:6]
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _ass_inline(value: str) -> str:
    r, g, b = _hex_rgb(value)
    return f"&H{b:02X}{g:02X}{r:02X}&"


def _pysubs_color(value: str) -> pysubs2.Color:
    r, g, b = _hex_rgb(value)
    return pysubs2.Color(r, g, b, 0)


def _capitalize(token: str) -> str:
    for i, ch in enumerate(token):
        if ch.isalpha():
            return token[:i] + ch.upper() + token[i + 1 :]
    return token


def case_words(tokens: list[str], mode: str) -> list[str]:
    """Apply a casing convention across a whole clip so sentence case is correct."""
    mode = (mode or "as-is").lower()
    if mode in ("upper", "caps", "all-caps"):
        return [t.upper() for t in tokens]
    if mode == "lower":
        return [t.lower() for t in tokens]
    if mode == "title":
        return [_capitalize(t) for t in tokens]
    if mode == "as-is":
        return list(tokens)

    # sentence case (default for non-caps styles)
    out: list[str] = []
    new_sentence = True
    for token in tokens:
        core = token.strip()
        low = core.lower()
        if low in _I_CONTRACTIONS:
            token = "I" + core[1:]
        elif new_sentence:
            token = _capitalize(token)
        elif re.search(r"\bi\b", token):
            token = re.sub(r"\bi\b", "I", token)
        out.append(token)
        new_sentence = bool(_SENTENCE_END.search(core)) or core.endswith((".", "!", "?"))
    return out


class CaptionParams(BaseModel):
    default_style: str = DEFAULT_CAPTION_STYLE
    add_titles: bool = True
    title_seconds: float = 3.0
    title_font: str = "Anton"
    platform: str = "shorts"          # shorts | reels | tiktok
    clamp_to_safe_area: bool = True


@register
class BuildCaptionsNode(Node):
    type = "build_captions"
    title = "Build Captions"
    category = "captions"
    description = "Generate styled .ass subtitles per clip from word timings."
    inputs = {"clips": "ClipList", "transcript": "Transcript"}
    outputs = {"ass_files": "Json", "ass_dir": "File"}
    params_model = CaptionParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        data = inputs.get("clips")
        transcript = inputs.get("transcript") or {}
        if not data:
            raise ValueError("build_captions requires clips input")

        clip_list = ClipList.model_validate(data)
        words = transcript.get("words") or []
        segments = transcript.get("segments") or []
        default_style = self.param("default_style", DEFAULT_CAPTION_STYLE)

        ass_dir = ctx.project.clips / "captions"
        ass_dir.mkdir(parents=True, exist_ok=True)

        mapping: dict[str, str] = {}
        for clip in clip_list.enabled_clips():
            style = CAPTION_PRESETS.get(clip.caption_style or default_style)
            if style is None:
                style = CAPTION_PRESETS[DEFAULT_CAPTION_STYLE]
            path = ass_dir / f"{clip.id}.ass"
            self._write_ass(path, clip, style, words, segments)
            mapping[clip.id] = str(path)

        ctx.progress(1.0, f"{len(mapping)} caption tracks")
        return {"ass_files": mapping, "ass_dir": str(ass_dir)}

    # -- helpers ------------------------------------------------------------
    def _safe_position(self, style: CaptionStyle) -> float:
        if not self.param("clamp_to_safe_area", True):
            return style.position
        bottom = PLATFORM_SAFE.get(self.param("platform", "shorts"), (0.08, 0.80))[1]
        return float(min(max(style.position, 0.50), min(bottom, UNIVERSAL_MAX_POSITION + 0.04) - 0.04))

    def _write_ass(
        self,
        path: Any,
        clip: Any,
        style: CaptionStyle,
        words: list[dict[str, Any]],
        segments: list[dict[str, Any]],
    ) -> None:
        subs = pysubs2.SSAFile()
        subs.info["PlayResX"] = "1080"
        subs.info["PlayResY"] = "1920"
        subs.info["WrapStyle"] = "0"       # smart wrapping (prevents overflow)
        subs.info["ScaledBorderAndShadow"] = "yes"

        s = subs.styles["Default"]
        s.fontname = style.font
        s.fontsize = style.font_size
        s.bold = style.bold
        s.italic = style.italic
        s.primarycolor = _pysubs_color(style.fill)
        s.outlinecolor = _pysubs_color(style.stroke)
        s.backcolor = _pysubs_color(style.box_color if style.box else "#000000")
        s.outline = float(style.stroke_width)
        s.shadow = float(style.shadow)
        s.borderstyle = 3 if style.box else 1
        s.alignment = pysubs2.Alignment.BOTTOM_CENTER
        s.marginv = int((1.0 - self._safe_position(style)) * 1920)
        s.marginl = style.margin_lr
        s.marginr = style.margin_lr

        if self.param("add_titles", True):
            self._add_title_style(subs)
            self._emit_title(subs, clip)

        clip_words = [
            w for w in words
            if w["start"] >= clip.start - 0.25 and w["end"] <= clip.end + 0.25
        ]

        if clip_words:
            tokens = case_words([w["word"].strip() for w in clip_words], style.case)
            if style.mode == "static":
                self._emit_segments(subs, clip, style, segments)
            elif style.mode == "karaoke":
                self._emit_word_beats(subs, clip, style, clip_words, tokens, animate=False)
            elif style.mode == "phrase":
                self._emit_phrase_beats(subs, clip, style, clip_words, tokens)
            else:  # "word"
                self._emit_word_beats(
                    subs, clip, style, clip_words, tokens, animate=style.animation == "pop"
                )
        else:
            self._emit_segments(subs, clip, style, segments)

        subs.save(str(path), format_="ass")

    def _add_title_style(self, subs: pysubs2.SSAFile) -> None:
        t = pysubs2.SSAStyle()
        t.fontname = self.param("title_font", "Anton")
        t.fontsize = 74
        t.bold = True
        t.primarycolor = _pysubs_color("#FFFFFF")
        t.outlinecolor = _pysubs_color("#000000")
        t.outline = 7.0
        t.shadow = 3.0
        t.borderstyle = 1
        t.alignment = pysubs2.Alignment.TOP_CENTER
        t.marginv = int(PLATFORM_SAFE.get(self.param("platform", "shorts"), (0.08, 0.80))[0] * 1920)
        t.marginl = 90
        t.marginr = 90
        subs.styles["Title"] = t

    def _emit_title(self, subs: pysubs2.SSAFile, clip: Any) -> None:
        text = (clip.title_text or clip.title or "").strip()
        if not text:
            return
        seconds = float(self.param("title_seconds", 3.0))
        end_ms = int(min(seconds, clip.duration) * 1000)
        body = (
            "{\\fad(180,120)\\fscx112\\fscy112"
            "\\t(0,220,\\fscx100\\fscy100)}" + text.upper()
        )
        subs.append(pysubs2.SSAEvent(start=0, end=end_ms, text=body, style="Title"))

    @staticmethod
    def _local_ms(clip: Any, t: float) -> int:
        return max(0, int(round((t - clip.start) * 1000)))

    def _beat_text(self, style: CaptionStyle, tokens: list[str], active: int | None = None) -> str:
        parts = []
        for i, token in enumerate(tokens):
            if active is not None and i == active and style.highlight:
                parts.append(
                    f"{{\\c{_ass_inline(style.highlight)}}}{token}{{\\c{_ass_inline(style.fill)}}}"
                )
            else:
                parts.append(token)
        return " ".join(parts)

    def _emit_phrase_beats(self, subs, clip, style, words, tokens) -> None:
        for i in range(0, len(words), style.max_words):
            beat_words = words[i : i + style.max_words]
            beat_tokens = tokens[i : i + style.max_words]
            text = self._beat_text(style, beat_tokens)
            subs.append(
                pysubs2.SSAEvent(
                    start=self._local_ms(clip, beat_words[0]["start"]),
                    end=self._local_ms(clip, beat_words[-1]["end"]),
                    text=text,
                    style="Default",
                )
            )

    def _emit_word_beats(self, subs, clip, style, words, tokens, animate: bool) -> None:
        for i in range(0, len(words), style.max_words):
            beat_words = words[i : i + style.max_words]
            beat_tokens = tokens[i : i + style.max_words]
            for j, word in enumerate(beat_words):
                start = max(beat_words[0]["start"], word["start"])
                end = (
                    beat_words[j + 1]["start"]
                    if j + 1 < len(beat_words)
                    else beat_words[-1]["end"]
                )
                if end <= start:
                    continue
                text = self._beat_text(style, beat_tokens, active=j)
                if animate:
                    peak = style.pop_scale
                    text = (
                        f"{{\\fscx{peak:.0f}\\fscy{peak:.0f}"
                        f"\\t(0,140,\\fscx100\\fscy100)}}" + text
                    )
                subs.append(
                    pysubs2.SSAEvent(
                        start=self._local_ms(clip, start),
                        end=self._local_ms(clip, end),
                        text=text,
                        style="Default",
                    )
                )

    def _emit_segments(self, subs, clip, style, segments) -> None:
        for seg in segments:
            if seg["end"] <= clip.start or seg["start"] >= clip.end:
                continue
            raw = seg["text"].strip()
            if not raw:
                continue
            text = " ".join(case_words(raw.split(), style.case))
            text = "{\\fad(120,80)}" + text
            subs.append(
                pysubs2.SSAEvent(
                    start=self._local_ms(clip, max(seg["start"], clip.start)),
                    end=self._local_ms(clip, min(seg["end"], clip.end)),
                    text=text,
                    style="Default",
                )
            )

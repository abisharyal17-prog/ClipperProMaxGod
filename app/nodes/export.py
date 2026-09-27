"""Transcript export.

Produces:
  * ``transcript.txt``  — timestamped plain transcript
  * ``transcript.srt``  — standard subtitles
  * ``payload.txt``     — the *enriched* transcript to paste into the external AI
  * ``prompt.txt``      — the instruction block + JSON contract for the AI

The prompt is model-agnostic and deliberately strict: it states the objective, the
selection criteria, a scoring rubric, exact boundary rules and a single JSON output
contract, so any capable assistant returns importable JSON on the first try.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.context import RunContext
from app.core.graph import Node
from app.core.registry import register

# ---------------------------------------------------------------------------
# The clip contract described to the external AI. Kept hand-written (not the full
# pydantic schema) so it is short, unambiguous and easy for any model to follow.
_CLIP_SCHEMA = """{
  "version": 1,
  "source": { "title": "string", "duration_seconds": 0 },
  "clips": [
    {
      "id": "clip_001",
      "title": "string, <= 6 words, honest (no lying clickbait)",
      "start": "MM:SS.mmm",
      "end": "MM:SS.mmm",
      "score": 0,
      "reason": "one sentence explaining why this moment works",
      "hook": "the exact first spoken line of the clip",
      "keywords": ["2-4 low-case keywords for hashtags"],
      "reframe": null,
      "caption_style": null,
      "lut": null,
      "title_text": null
    }
  ]
}"""

_CLIP_EXAMPLE = """{
  "version": 1,
  "source": { "title": "Example video", "duration_seconds": 294.4 },
  "clips": [
    {
      "id": "clip_001",
      "title": "The pricing mistake",
      "start": "06:52.350",
      "end": "07:35.100",
      "score": 88,
      "reason": "Opens with a contrarian claim and pays it off with a concrete number.",
      "hook": "The single biggest mistake is pricing too low",
      "keywords": ["pricing", "revenue"],
      "reframe": "crop",
      "caption_style": "hormozi",
      "lut": "cinematic",
      "title_text": null
    }
  ]
}"""


def build_prompt(n_clips: int = 8, min_dur: int = 15, max_dur: int = 60) -> str:
    return f"""You are an elite short-form video editor. You have cut thousands of
viral YouTube Shorts, TikToks and Reels, and you know exactly what makes a muted
viewer stop scrolling in the first second and watch to the end.

# OBJECTIVE
From the transcript below, select up to {n_clips} of the strongest, most self-contained
moments and return them as structured JSON that I will import directly into my editor.
Quality beats quantity: return fewer, better clips rather than padding the list.

# WHAT MAKES A GREAT CLIP
- HOOK: the first 1-2 seconds create a curiosity gap, a bold claim, a question, a
  number, or a strong emotion. Never open on throat-clearing or "so, um".
- SELF-CONTAINED: it makes sense with zero outside context.
- PAYOFF: it resolves — a punchline, a reveal, a lesson, a result.
- ENERGY / EMOTION: laughter, surprise, tension, conviction, or a hot take.
- QUOTABLE: at least one line you would screenshot.
- MOMENTUM: minimal filler; the value arrives fast.

# HARD RULES (must all hold)
1. Duration of every clip: between {min_dur} and {max_dur} seconds.
2. Start on a sentence boundary or a natural hook line — NEVER mid-word or mid-sentence.
3. End on a COMPLETE thought — NEVER cut a sentence in half.
4. Clips must NOT overlap.
5. Every timestamp MUST come from the transcript below. Do not invent times.
6. Prefer boundaries that fall on a [SIL] silence gap, a [CUT] scene change, or the
   end of a sentence, so the cut is clean.
7. Return ONLY the JSON object. No markdown fences, no explanation, no extra text.

# HOW TO CHOOSE THE BOUNDARIES
- Start 0.0-1.0s before the hook line (a tiny lead-in is good; more is not).
- End right after the payoff line, before the topic drifts.
- Use millisecond precision copied from the transcript timestamps.

# SCORING (0-100) - sum of these weights
- Hook strength ....... up to 30
- Self-containment .... up to 20
- Emotional payoff ..... up to 20
- Informational value .. up to 15
- Quotability .......... up to 15

# INPUT FORMAT
Each transcript line looks like:  [HH:MM:SS.mmm] spoken text
Special markers appear on their own lines:
  [SIL n.ns]  = a silence gap of n.n seconds (a natural cut point)
  [CUT]       = a scene / shot change (a natural transition)

# OUTPUT CONTRACT
Return a single JSON object matching this schema exactly:
{_CLIP_SCHEMA}

Field notes:
- "start"/"end": "MM:SS.mmm" or "HH:MM:SS.mmm". Must exist in the transcript.
- "reframe": one of null (auto), "crop" (talking head), "blur" (keep full frame on a
  blurred background), "pad". Use null unless a specific one clearly fits.
- "caption_style": one of null, "hormozi", "karaoke", "dynamic-minimal", "beast",
  "neon", "clean". Use null to inherit my default.
- "lut": one of null, "cinematic", "teal-orange", "warm-film", "cool-film", "kodak",
  "fuji", "fade", "vibrant", "noir", "neutral". Use null to inherit my default.
- "title_text": optional BIG on-screen hook text (<= 5 words); null means use "title".

A complete example of the expected output:
{_CLIP_EXAMPLE}

# FINAL REMINDERS
- JSON only. Start with {{ and end with }}.
- If the transcript only contains fewer than {n_clips} good moments, return only those.
- Never exceed {max_dur}s and never go under {min_dur}s.
- If you are unsure about a timestamp, choose the nearest sentence boundary.

# TRANSCRIPT
{{transcript_placeholder}}
"""


def _compact(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _clock(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _srt_clock(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        s, ms = s + 1, 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class ExportTranscriptParams(BaseModel):
    n_clips: int = 8
    min_duration: int = 15
    max_duration: int = 60
    include_markers: bool = True


@register
class ExportTranscriptNode(Node):
    type = "export_transcript"
    title = "Export Transcript"
    category = "output"
    description = "Write transcript.txt / .srt and the enriched AI payload + prompt."
    inputs = {
        "transcript": "Transcript",
        "events": "Json",
        "scenes": "Json",
        "meta": "Json",
    }
    outputs = {
        "transcript_txt": "File",
        "transcript_srt": "File",
        "payload_txt": "File",
        "prompt_txt": "File",
        "combined_txt": "File",
    }
    params_model = ExportTranscriptParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        transcript = inputs.get("transcript")
        if not transcript:
            raise ValueError("export_transcript requires a transcript input")
        events = inputs.get("events") or {}
        scenes = inputs.get("scenes") or {}
        meta = inputs.get("meta") or {}

        segments = transcript.get("segments", [])
        txt_path = ctx.project.transcript / "transcript.txt"
        srt_path = ctx.project.transcript / "transcript.srt"
        payload_path = ctx.project.transcript / "payload.txt"
        prompt_path = ctx.project.transcript / "prompt.txt"
        combined_path = ctx.project.transcript / "prompt_and_transcript.txt"

        txt_lines = [f"[{_clock(s['start'])}] {s['text']}" for s in segments]
        txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

        srt_blocks = []
        for i, s in enumerate(segments, start=1):
            srt_blocks.append(
                f"{i}\n{_srt_clock(s['start'])} --> {_srt_clock(s['end'])}\n{s['text']}\n"
            )
        srt_path.write_text("\n".join(srt_blocks), encoding="utf-8")

        payload = self._payload(transcript, events, scenes, meta)
        payload_path.write_text(payload, encoding="utf-8")

        prompt = build_prompt(
            n_clips=self.param("n_clips", 8),
            min_dur=self.param("min_duration", 15),
            max_dur=self.param("max_duration", 60),
        )
        prompt_path.write_text(prompt, encoding="utf-8")

        # One blob to copy in a single click: instructions + transcript together.
        combined = prompt.replace("{transcript_placeholder}", payload)
        combined_path.write_text(combined, encoding="utf-8")

        ctx.progress(1.0, "transcript + payload + prompt written")
        return {
            "transcript_txt": str(txt_path),
            "transcript_srt": str(srt_path),
            "payload_txt": str(payload_path),
            "prompt_txt": str(prompt_path),
            "combined_txt": str(combined_path),
        }

    def _payload(
        self,
        transcript: dict[str, Any],
        events: dict[str, Any],
        scenes: dict[str, Any],
        meta: dict[str, Any],
    ) -> str:
        dur = transcript.get("duration") or meta.get("duration") or 0.0
        header = [
            "# VIDEO",
            f"duration: {_clock(dur)}  ({dur:.1f}s)" if dur else "duration: unknown",
            f"language: {transcript.get('language')}",
            f"resolution: {meta.get('width')}x{meta.get('height')}"
            if meta.get("width")
            else "resolution: unknown",
        ]
        lufs = events.get("lufs")
        if lufs is not None:
            header.append(f"loudness: {lufs:.1f} LUFS")

        markers = self.param("include_markers", True)
        header.append("")
        header.append(
            "markers: [SIL n.ns] silence gap, [CUT] scene change"
            if markers
            else "markers: disabled"
        )
        header.append("# TRANSCRIPT (mm:ss.sss)")

        silences = sorted(events.get("silences", []), key=lambda r: r[0]) if markers else []
        cuts = sorted(scenes.get("cuts", [])) if markers else []
        segments = transcript.get("segments", [])

        lines: list[str] = []
        prev_end = 0.0
        for seg in segments:
            start = float(seg["start"])
            if markers:
                for sil in silences:
                    if prev_end - 0.05 <= sil[0] < start and sil[1] - sil[0] >= 0.4:
                        lines.append(f"    [SIL {sil[1] - sil[0]:.1f}s]")
                for cut in cuts:
                    if prev_end < cut < start:
                        lines.append("    [CUT]")
            lines.append(f"[{_clock(start)}] {seg['text']}")
            prev_end = float(seg["end"])

        return "\n".join(header + lines) + "\n"

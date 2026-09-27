"""Rendering: turn one clip spec into a finished vertical video.

Composable ffmpeg filter graph per clip:

    trim / concat -> reset PTS -> reframe -> captions -> LUT -> loudness -> encode

Reframe modes: ``crop`` (subject-centred, with a smoothed dynamic camera path when
the subject moves), ``blur`` (blurred background fill) and ``pad``. Audio is
normalised to the platform target with a two-pass loudnorm measurement.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app import paths
from app.core.context import RunContext
from app.core.graph import Node
from app.core.registry import register
from app.schema import ClipList

MAX_SENDCMD_POINTS = 40  # keep nested-expression depth safely under ffmpeg's parser limit
DYNAMIC_MOTION_FRACTION = 0.04  # subject must move >4% of frame width to pan


def _complement(start: float, end: float, ranges: Iterable) -> list[tuple[float, float]]:
    segments: list[tuple[float, float]] = []
    cursor = start
    for a, b in sorted((max(a, start), min(b, end)) for a, b in ranges):
        if b <= a:
            continue
        if a > cursor:
            segments.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < end:
        segments.append((cursor, end))
    return segments or [(start, end)]


def _esc_filter_path(path: str | Path) -> str:
    s = str(path).replace("\\", "/")
    return s.replace(":", "\\:").replace("'", "\\'")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class RenderParams(BaseModel):
    default_reframe: str = "auto"
    default_lut: str | None = None
    default_music: str | None = None
    music_volume: float = 1.0          # taste multiplier applied to a normalised bed
    music_lufs: float = -16.0          # music bed is normalised to this level first
    duck_threshold: float = 0.20
    duck_ratio: float = 8.0
    duck_music: bool = True
    dynamic_camera: bool = True
    two_pass_loudnorm: bool = True


@register
class RenderClipsNode(Node):
    type = "render_clips"
    title = "Render Clips"
    category = "output"
    description = "Trim, reframe to 9:16, burn captions, normalise loudness and encode."
    inputs = {
        "media": "MediaFile",
        "clips": "ClipList",
        "ass_files": "Json",
        "meta": "Json",
        "tracks": "Tracks",
    }
    outputs = {"renders": "Json", "render_dir": "File"}
    params_model = RenderParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        media = inputs.get("media")
        data = inputs.get("clips")
        if not media or not data:
            raise ValueError("render_clips requires media and clips inputs")
        ass_files: dict[str, str] = inputs.get("ass_files") or {}
        tracks: dict[str, Any] = inputs.get("tracks") or {}
        meta = inputs.get("meta") or {}

        clip_list = ClipList.model_validate(data)
        clips = clip_list.enabled_clips()
        settings = ctx.settings.render
        src = (int(meta.get("width") or 1920), int(meta.get("height") or 1080))
        has_audio = bool(meta.get("has_audio", True))
        out_size = (settings.width, settings.height)
        outputs: list[dict[str, Any]] = []

        total = max(1, len(clips))
        for index, clip in enumerate(clips):
            ctx.check_cancel()
            report = ctx.child_progress(index / total, (index + 1) / total)
            out_path = ctx.project.render / f"{clip.id}.mp4"

            reframe = clip.reframe or self.param("default_reframe", "auto")
            if reframe == "auto":
                reframe = "crop"
            lut = self._resolve_asset(
                clip.lut or self.param("default_lut") or clip_list.defaults.lut, paths.LUTS_DIR, ".cube"
            )
            music = self._resolve_music(clip.music or self.param("default_music") or clip_list.defaults.music)
            segments = _complement(float(clip.start), float(clip.end), clip.exclude_ranges)
            duration = sum(b - a for a, b in segments)

            simple = len(segments) == 1
            plan = self._crop_plan(ctx, clip, tracks.get(clip.id), src, out_size, simple)
            ctx.log(
                f"[{index + 1}/{total}] {clip.id} {clip.start:.2f}-{clip.end:.2f}s "
                f"({duration:.1f}s) reframe={reframe} cam={plan['mode']}"
            )

            loudness = None
            if has_audio and self.param("two_pass_loudnorm", True):
                loudness = self._measure(ctx, media, segments, settings, music)

            args = self._build(
                media=media,
                segments=segments,
                reframe=reframe,
                lut=lut,
                ass_path=ass_files.get(clip.id),
                settings=settings,
                out_path=out_path,
                plan=plan,
                has_audio=has_audio,
                loudness=loudness,
                duration=duration,
                music=music,
            )
            ctx.ffmpeg.run(
                args,
                duration=duration,
                on_progress=lambda f, _r=report: _r(f, "encoding"),
                description=f"render {clip.id}",
            )
            outputs.append(
                {
                    "clip_id": clip.id,
                    "path": str(out_path),
                    "duration": round(duration, 3),
                    "title": clip.title,
                    "reframe": reframe,
                    "camera": plan["mode"],
                }
            )
            report(1.0, "done")

        manifest = ctx.project.render / "render.json"
        manifest.write_text(json.dumps({"clips": outputs}, indent=2), encoding="utf-8")
        ctx.progress(1.0, f"{len(outputs)} clips rendered")
        return {"renders": outputs, "render_dir": str(ctx.project.render)}

    # -- asset resolution ---------------------------------------------------
    def _resolve_music(self, value: str | None) -> str | None:
        return self._resolve_asset(value, paths.MUSIC_DIR, ".mp3")

    def _resolve_asset(self, value: str | None, folder: Path, suffix: str) -> str | None:
        if not value:
            return None
        candidate = Path(value)
        if candidate.is_absolute() and candidate.exists():
            return str(candidate)
        for cand in (folder / value, folder / f"{value}{suffix}", candidate):
            if cand.exists():
                return str(cand)
        return None

    def _crop_xy(
        self, src: tuple[int, int], out: tuple[int, int], center: tuple[float, float]
    ) -> tuple[float, float]:
        sw_src, sh_src = src
        W, H = out
        if sw_src <= 0 or sh_src <= 0:
            return 0.0, 0.0
        scale = max(W / sw_src, H / sh_src)
        scaled_w, scaled_h = sw_src * scale, sh_src * scale
        cx, cy = center
        x = _clamp(cx * scaled_w - W / 2, 0.0, max(0.0, scaled_w - W))
        y = _clamp(cy * scaled_h - H / 2, 0.0, max(0.0, scaled_h - H))
        return x, y

    def _crop_plan(
        self,
        ctx: RunContext,
        clip: Any,
        track: dict[str, Any] | None,
        src: tuple[int, int],
        out: tuple[int, int],
        simple: bool,
    ) -> dict[str, Any]:
        x, y = self._crop_xy(src, out, (0.5, 0.5))
        if not track or not track.get("times"):
            return {"mode": "static", "x": round(x, 1), "y": round(y, 1)}

        xs_raw = track.get("cx") or []
        ys_raw = track.get("cy") or []
        if not xs_raw:
            return {"mode": "static", "x": round(x, 1), "y": round(y, 1)}

        points: list[tuple[float, float, float]] = []
        for t, cx, cy in zip(track["times"], xs_raw, ys_raw, strict=False):
            px, py = self._crop_xy(src, out, (cx, cy))
            # track times are already clip-local (t=0 is the clip start)
            points.append((float(t), px, py))
        points = [p for p in points if p[0] >= -0.05]
        if not points:
            return {"mode": "static", "x": round(x, 1), "y": round(y, 1)}
        if points[0][0] > 0:
            points.insert(0, (0.0, points[0][1], points[0][2]))

        motion = max(p[1] for p in points) - min(p[1] for p in points)
        W = out[0]
        if not self.param("dynamic_camera", True) or not simple or motion < W * DYNAMIC_MOTION_FRACTION:
            mid = sorted(xs_raw)[len(xs_raw) // 2]
            mid_y = sorted(ys_raw)[len(ys_raw) // 2] if ys_raw else 0.5
            sx, sy = self._crop_xy(src, out, (mid, mid_y))
            return {"mode": "static", "x": round(sx, 1), "y": round(sy, 1)}

        step = max(1, math.ceil(len(points) / MAX_SENDCMD_POINTS))
        sampled = points[::step]
        if sampled[-1][0] < points[-1][0]:
            sampled.append(points[-1])
        ts = [p[0] for p in sampled]
        xs = [p[1] for p in sampled]
        ys = [p[2] for p in sampled]
        return {
            "mode": "dynamic",
            "x": int(round(xs[0])),
            "y": int(round(ys[0])),
            "xexpr": self._curve_expr(ts, xs),
            "yexpr": self._curve_expr(ts, ys),
        }

    @staticmethod
    def _curve_expr(times: list[float], values: list[float]) -> str:
        """A piecewise-linear ffmpeg expression in ``t`` for a sample series.

        Values are rounded to whole pixels: crop at integer offsets avoids per-frame
        sub-pixel resampling (which reads as shimmer), and 1px steps are invisible at
        a 3413px working width.
        """
        n = len(values)
        if n == 0:
            return "0"
        if n == 1:
            return f"{values[0]:.0f}"
        expr = f"{values[-1]:.0f}"
        for i in range(n - 2, -1, -1):
            t1 = times[i + 1]
            dt = max(1e-3, t1 - times[i])
            seg = f"lerp({values[i]:.0f},{values[i + 1]:.0f},(t-{times[i]:.3f})/{dt:.3f})"
            expr = f"if(lt(t,{t1:.3f}),{seg},{expr})"
        return expr

    # -- loudness -----------------------------------------------------------
    def _mix_filters(
        self,
        abase: str,
        music_index: int | None,
        duration: float,
        ln: str,
    ) -> list[str]:
        """Speech (+ optional ducked music) mixed, then loudness-normalised last.

        Normalising the final mix (not just the voice) keeps the output on target
        whether or not a music bed is present.
        """
        out: list[str] = [f"{abase}highpass=f=80[sp]"]
        if music_index is not None:
            volume = float(self.param("music_volume", 1.0))
            bed_lufs = float(self.param("music_lufs", -16.0))
            out.append("[sp]asplit=2[voice][key]")
            out.append(
                f"[{music_index}:a]atrim=0:{duration:.3f},"
                f"loudnorm=I={bed_lufs}:TP=-2:LRA=11,volume={volume:.3f}[mus]"
            )
            if self.param("duck_music", True):
                thr = float(self.param("duck_threshold", 0.20))
                ratio = float(self.param("duck_ratio", 8.0))
                out.append(
                    f"[mus][key]sidechaincompress=threshold={thr}:ratio={ratio}"
                    ":attack=20:release=400:makeup=1[bed]"
                )
            else:
                out.append("[mus]anull[bed]")
            out.append("[voice][bed]amix=inputs=2:duration=first:normalize=0[pre]")
        else:
            out.append("[sp]anull[pre]")
        out.append(f"[pre]{ln}[aout]")
        return out

    def _measure(
        self,
        ctx: RunContext,
        media: str,
        segments: list[tuple[float, float]],
        settings: Any,
        music: str | None,
    ) -> dict[str, float] | None:
        duration = sum(b - a for a, b in segments)
        inputs: list[str] = []
        for start, end in segments:
            inputs += ["-ss", f"{start:.3f}", "-t", f"{max(0.0, end - start):.3f}", "-i", str(media)]
        music_index = None
        if music:
            music_index = len(segments)
            inputs += ["-stream_loop", "-1", "-i", str(music)]

        filters: list[str] = []
        if len(segments) == 1:
            abase = "[0:a]"
        else:
            cin = "".join(f"[{i}:a]" for i in range(len(segments)))
            filters.append(f"{cin}concat=n={len(segments)}:v=0:a=1[ac]")
            abase = "[ac]"
        ln = f"loudnorm=I={settings.audio_lufs}:TP=-1.5:LRA=11:print_format=json"
        filters += self._mix_filters(abase, music_index, duration, ln)
        try:
            return ctx.ffmpeg.measure_loudness(inputs, ";".join(filters), [])
        except RuntimeError as exc:  # noqa: BLE001 - measurement is best-effort
            ctx.log(f"loudnorm measure failed, using single pass: {exc}", level="warn")
            return None

    # -- ffmpeg command -----------------------------------------------------
    def _build(
        self,
        *,
        media: str,
        segments: list[tuple[float, float]],
        reframe: str,
        lut: str | None,
        ass_path: str | None,
        settings: Any,
        out_path: Path,
        plan: dict[str, Any],
        has_audio: bool,
        loudness: dict[str, float] | None,
        duration: float,
        music: str | None,
    ) -> list[str]:
        W, H = settings.width, settings.height
        args: list[str] = []
        for start, end in segments:
            args += ["-ss", f"{start:.3f}", "-t", f"{max(0.0, end - start):.3f}", "-i", str(media)]
        silence_index = None
        if not has_audio:
            silence_index = len(segments)
            args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]

        filters: list[str] = []
        if len(segments) == 1:
            vbase, abase = "[0:v]", ("[0:a]" if has_audio else f"[{silence_index}:a]")
        else:
            concat_in = "".join(f"[{i}:v][{i}:a]" for i in range(len(segments)))
            filters.append(f"{concat_in}concat=n={len(segments)}:v=1:a=1[vc][ac]")
            vbase, abase = "[vc]", "[ac]"

        filters.append(f"{vbase}setpts=PTS-STARTPTS[v0]")
        vbase = "[v0]"

        if reframe == "blur":
            filters.append(
                f"{vbase}split=2[bg0][fg0];"
                f"[bg0]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},boxblur=luma_radius=32:luma_power=1:chroma_radius=16[bg];"
                f"[fg0]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2[vref]"
            )
        elif reframe == "pad":
            filters.append(
                f"{vbase}scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black[vref]"
            )
        else:
            x, y = plan["x"], plan["y"]
            if plan["mode"] == "dynamic":
                xexpr, yexpr = plan["xexpr"], plan["yexpr"]
                filters.append(
                    f"{vbase}scale={W}:{H}:force_original_aspect_ratio=increase,"
                    f"crop={W}:{H}:x='{xexpr}':y='{yexpr}'[vref]"
                )
            else:
                filters.append(
                    f"{vbase}scale={W}:{H}:force_original_aspect_ratio=increase,"
                    f"crop={W}:{H}:{x}:{y}[vref]"
                )

        current = "vref"
        if ass_path:
            ass_esc = _esc_filter_path(ass_path)
            fontsdir = _esc_filter_path(paths.FONTS_DIR)
            filters.append(f"[{current}]ass=filename='{ass_esc}':fontsdir='{fontsdir}'[vcap]")
            current = "vcap"
        if lut:
            filters.append(f"[{current}]lut3d=file='{_esc_filter_path(lut)}'[vlut]")
            current = "vlut"

        music_index = None
        if music:
            music_index = len(segments) + (1 if not has_audio else 0)
            args += ["-stream_loop", "-1", "-i", str(music)]
        filters += self._mix_filters(
            abase, music_index, duration, self._loudnorm(settings, loudness)
        )

        args += ["-filter_complex", ";".join(filters), "-map", f"[{current}]", "-map", "[aout]"]
        if settings.fps:
            args += ["-r", str(settings.fps)]

        if settings.encoder == "h264_nvenc":
            args += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", str(settings.crf)]
        else:
            args += ["-c:v", "libx264", "-crf", str(settings.crf), "-preset", settings.preset]
        args += ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", settings.audio_bitrate]
        if settings.faststart:
            args += ["-movflags", "+faststart"]
        return args + [str(out_path)]

    @staticmethod
    def _loudnorm(settings: Any, measured: dict[str, float] | None) -> str:
        base = f"loudnorm=I={settings.audio_lufs}:TP=-1.5:LRA=11"
        if not measured:
            return base
        return (
            base
            + f":measured_I={measured['input_i']}"
            + f":measured_TP={measured['input_tp']}"
            + f":measured_LRA={measured['input_lra']}"
            + f":measured_thresh={measured['input_thresh']}"
            + f":offset={measured['target_offset']}"
            + ":linear=true"
        )

"""Subject tracking: keep the speaker's face in frame.

Primary signal is a real face detector (OpenCV YuNet) — accurate and fast, unlike
Haar cascades which produced false positives that dragged the crop off the
speaker. Faces are chosen with continuity bias so the crop doesn't jump between
people. When no face is found, we fall back to the head region (upper part) of the
largest detected person box. The resulting centre path is smoothed.

Runs only when the ``ml`` extra is installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app import paths
from app.core.context import RunContext
from app.core.graph import Node
from app.core.registry import register
from app.schema import ClipList

_YUNET_DEFAULT = "face_detection_yunet_2023mar.onnx"


class TrackParams(BaseModel):
    weights: str = "yolov8n.pt"                 # person fallback
    face_model: str = _YUNET_DEFAULT            # YuNet face detector
    conf: float = 0.3
    face_score: float = 0.6
    sample_fps: float = 10.0
    imgsz: int = 640
    y_bias: float = 0.10          # crop centre sits this far below the face -> face higher in frame
    head_ratio: float = 0.16      # fallback: head centre at this fraction of the person box height
    centrality_weight: float = 0.4
    # camera stabilisation (One Euro + hold zone + velocity limit) -> removes stutter
    min_cutoff: float = 0.9       # lower = smoother / more lag
    beta: float = 0.03            # higher = follows fast motion more closely
    dead_zone: float = 0.045      # hold the camera while the subject stays within this band
    max_velocity: float = 0.9     # max normalised units per second the camera may move


@register
class TrackSubjectNode(Node):
    type = "track_subject"
    title = "Track Subject"
    category = "video"
    description = "Face-first subject tracking (YuNet) into a smoothed centre path."
    inputs = {"media": "MediaFile", "clips": "ClipList", "meta": "Json"}
    outputs = {"tracks": "Tracks", "tracks_file": "File"}
    params_model = TrackParams

    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        media = inputs.get("media")
        data = inputs.get("clips")
        if not media or not data:
            raise ValueError("track_subject requires media and clips inputs")

        try:
            import cv2  # type: ignore
            import numpy as np
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Tracking needs the ml extra. Run: uv sync --extra ml") from exc

        clip_list = ClipList.model_validate(data)
        clips = clip_list.enabled_clips()

        face_model_path = self._model_path(self.param("face_model", _YUNET_DEFAULT))
        detector = None
        if face_model_path.exists():
            detector = cv2.FaceDetectorYN.create(
                str(face_model_path), "", (320, 320),
                score_threshold=float(self.param("face_score", 0.6)),
                nms_threshold=0.3, top_k=5000,
            )
        else:
            ctx.log(f"face model not found at {face_model_path}; using person-box fallback", level="warn")

        person_model = None
        weights = self._model_path(self.param("weights", "yolov8n.pt"))
        person_model = YOLO(str(weights))

        cap = cv2.VideoCapture(str(media))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(fps / float(self.param("sample_fps", 6.0)))))

        tracks: dict[str, Any] = {}
        total = max(1, len(clips))
        for index, clip in enumerate(clips):
            report = ctx.child_progress(index / total, (index + 1) / total)
            path = self._track_clip(
                ctx, cap, detector, person_model, cv2, np, clip, step, report
            )
            tracks[clip.id] = path
            report(1.0, f"{clip.id}: {len(path['cx'])} samples")

        cap.release()
        out = ctx.project.tracking / "tracks.json"
        out.write_text(json.dumps(tracks, indent=2), encoding="utf-8")
        ctx.progress(1.0, f"tracked {len(tracks)} clips")
        return {"tracks": tracks, "tracks_file": str(out)}

    # -- per clip ----------------------------------------------------------
    def _track_clip(self, ctx, cap, detector, person_model, cv2, np, clip, step, report):
        cap.set(cv2.CAP_PROP_POS_MSEC, clip.start * 1000.0)
        times: list[float] = []
        cxs: list[float] = []
        cys: list[float] = []
        prev_cx: float | None = None
        frame_idx = 0
        span = max(0.1, clip.end - clip.start)

        while True:
            if not cap.grab():
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if t > clip.end:
                break
            if frame_idx % step == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                h, w = frame.shape[:2]
                target = self._face_target(detector, cv2, np, frame, w, h, prev_cx)
                if target is None:
                    target = self._person_head(person_model, frame, w, h)
                if target is not None:
                    prev_cx = target[0] if prev_cx is None else 0.7 * prev_cx + 0.3 * target[0]
                    times.append(round(t - clip.start, 3))
                    cxs.append(float(target[0]))
                    cys.append(float(target[1]))
                report(min(1.0, (t - clip.start) / span), "tracking")
            frame_idx += 1

        series = self._smooth(np, times, cxs, cys)
        return series

    def _face_target(self, detector, cv2, np, frame, w, h, prev_cx):
        if detector is None:
            return None
        detector.setInputSize((w, h))
        _, faces = detector.detect(frame)
        if faces is None or not len(faces):
            return None
        best, best_score = None, -1.0
        for f in faces:
            x, y, bw, bh, score = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[-1])
            area = (bw * bh) / (w * h)
            cx = (x + bw / 2) / w
            cy = (y + bh / 2) / h
            continuity = 1.0 - (0.0 if prev_cx is None else min(1.0, abs(cx - prev_cx)))
            s = (0.5 + score) * (0.4 + area) * (0.5 + 0.5 * continuity)
            if s > best_score:
                best_score, best = s, (cx, cy)
        if best is None:
            return None
        return (best[0], min(1.0, best[1] + float(self.param("y_bias", 0.10))))

    def _person_head(self, person_model, frame, w, h):
        results = person_model.predict(
            frame, classes=[0], conf=self.param("conf", 0.3),
            imgsz=self.param("imgsz", 640), verbose=False,
        )
        boxes = results[0].boxes if results else None
        if boxes is None or not len(boxes):
            return None
        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        best, best_score = None, -1.0
        weight = float(self.param("centrality_weight", 0.4))
        for (x1, y1, x2, y2), c in zip(xyxy, confs, strict=False):
            bw, bh = x2 - x1, y2 - y1
            area = (bw * bh) / (w * h)
            cx = ((x1 + x2) / 2) / w
            centrality = 1.0 - abs(cx - 0.5) * 2
            s = area * float(c) * ((1 - weight) + weight * centrality)
            if s > best_score:
                head_cy = (y1 + bh * float(self.param("head_ratio", 0.16))) / h
                best_score, best = s, (cx, min(1.0, head_cy))
        return best

    def _smooth(self, np, times, cxs, cys) -> dict[str, Any]:
        if not times:
            return {"times": [], "cx": [], "cy": []}

        import math

        t = np.array(times)
        x = np.array(cxs)
        y = np.array(cys)
        sample_fps = max(1.0, float(self.param("sample_fps", 10.0)))
        grid = np.arange(t[0], t[-1] + 1e-6, 1.0 / sample_fps)
        if len(grid) < 2:
            return {
                "times": [round(float(v), 3) for v in grid],
                "cx": [round(float(v), 4) for v in x],
                "cy": [round(float(v), 4) for v in y],
            }
        gx = np.interp(grid, t, x)
        gy = np.interp(grid, t, y)

        # 1) One Euro filter: removes jitter without adding the lag of a moving average
        gx = self._one_euro(gx, 1.0 / sample_fps, math, np)
        gy = self._one_euro(gy, 1.0 / sample_fps, math, np)

        # 2) Hold zone + velocity limit: the camera stays put for small wobble and
        #    glides (never teleports) when the subject moves.
        gx = self._stabilise(gx, 1.0 / sample_fps, math)
        gy = self._stabilise(gy, 1.0 / sample_fps, math)

        return {
            "times": [round(float(v), 3) for v in grid],
            "cx": [round(float(v), 4) for v in gx],
            "cy": [round(float(v), 4) for v in gy],
        }

    def _one_euro(self, values, dt, math, np):
        min_cutoff = float(self.param("min_cutoff", 0.9))
        beta = float(self.param("beta", 0.03))
        d_cutoff = 1.0

        def alpha(cutoff):
            tau = 1.0 / (2.0 * math.pi * cutoff)
            return 1.0 / (1.0 + tau / dt)

        x_prev = float(values[0])
        dx_prev = 0.0
        out = []
        for v in values:
            v = float(v)
            dx = (v - x_prev) / dt
            a_d = alpha(d_cutoff)
            dx_hat = a_d * dx + (1.0 - a_d) * dx_prev
            cutoff = min_cutoff + beta * abs(dx_hat)
            a = alpha(cutoff)
            x_hat = a * v + (1.0 - a) * x_prev
            out.append(x_hat)
            x_prev, dx_prev = x_hat, dx_hat
        return np.array(out)

    def _stabilise(self, values, dt, math):
        dead_zone = float(self.param("dead_zone", 0.045))
        max_velocity = float(self.param("max_velocity", 0.9))
        cam = float(values[0])
        out = []
        for v in values:
            v = float(v)
            gap = v - cam
            if abs(gap) > dead_zone:
                step = gap - math.copysign(dead_zone, gap)
                limit = max_velocity * dt
                if abs(step) > limit:
                    step = math.copysign(limit, step)
                cam += step
            out.append(cam)
        return out

    @staticmethod
    def _model_path(name: str) -> Path:
        p = Path(name)
        if p.is_absolute():
            return p
        target = paths.ROOT / "assets" / "models" / p.name
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

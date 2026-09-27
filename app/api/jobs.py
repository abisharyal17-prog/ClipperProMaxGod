"""In-process job registry.

The pipeline engine is synchronous, so each job runs inside a ``threading.Thread``.
The engine's ``emit(**kwargs)`` callback is bridged into :class:`~app.api.schemas.JobEvent`
records that are appended to the job, replayed to new WebSocket subscribers and
broadcast to live ones. A single lock guards the registry; ASGI delivery is
thread-safe via ``loop.call_soon_threadsafe``.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app import paths
from app.api import projects
from app.api.schemas import Job, JobEvent
from app.core.context import Cancelled
from app.pipeline.definitions import analysis_graph, render_graph
from app.run import run_graph

TERMINAL = {"done", "error", "cancelled"}
_INTERRUPTED = "The engine restarted before this job finished."


def _jobs_dir(project_id: str) -> Path:
    return projects.project_dir(project_id) / "jobs"


def _persist(job: Job) -> None:
    """Write a job's record to disk so history survives an engine restart."""
    try:
        directory = _jobs_dir(job.project_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{job.id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job.model_dump()), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass  # history is best-effort; never fail a job over it


def _from_disk(path: Path) -> Job | None:
    try:
        job = Job.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
    if job.status in {"queued", "running"}:
        # No thread is driving a job loaded from disk after a restart.
        job.status = "error"
        job.error = _INTERRUPTED
    return job


def _load_project_jobs(project_id: str) -> list[Job]:
    directory = _jobs_dir(project_id)
    if not directory.is_dir():
        return []
    jobs: list[Job] = []
    for path in directory.glob("*.json"):
        job = _from_disk(path)
        if job is not None:
            jobs.append(job)
    return jobs



@dataclass
class _Record:
    job: Job
    cancel: threading.Event = field(default_factory=threading.Event)
    subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = field(
        default_factory=list
    )
    thread: threading.Thread | None = None


class JobRegistry:
    """Thread-safe registry of running/finished jobs and their subscribers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, _Record] = {}

    # -- lifecycle ---------------------------------------------------------
    def create(self, project_id: str, stage: str) -> Job:
        job = Job(
            id=uuid.uuid4().hex,
            project_id=project_id,
            stage=stage,  # type: ignore[arg-type]
            status="queued",
            created=time.time(),
        )
        record = _Record(job=job)
        with self._lock:
            self._records[job.id] = record
        _persist(job)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            record = self._records.get(job_id)
            if record is not None:
                return record.job
        return self._find_on_disk(job_id)

    def _find_on_disk(self, job_id: str) -> Job | None:
        base = paths.PROJECTS
        if not base.is_dir():
            return None
        for project_dir in base.iterdir():
            candidate = project_dir / "jobs" / f"{job_id}.json"
            if candidate.is_file():
                return _from_disk(candidate)
        return None

    def list_for_project(self, project_id: str) -> list[Job]:
        with self._lock:
            live = [
                rec.job for rec in self._records.values()
                if rec.job.project_id == project_id
            ]
        merged: dict[str, Job] = {job.id: job for job in _load_project_jobs(project_id)}
        merged.update({job.id: job for job in live})
        jobs = sorted(merged.values(), key=lambda job: job.created, reverse=True)
        return jobs

    def cancel(self, job_id: str) -> Job | None:
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                return None
            record.cancel.set()
            return record.job

    # -- events ------------------------------------------------------------
    def add_event(self, job_id: str, event: JobEvent) -> None:
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                return
            record.job.events.append(event)
            subscribers = list(record.subscribers)
        _dispatch(subscribers, event.model_dump())

    def subscribe(
        self, job_id: str, loop: asyncio.AbstractEventLoop
    ) -> tuple[list[dict[str, Any]], asyncio.Queue | None, str | None] | None:
        """Replay existing events and register a queue for future ones.

        Returns ``None`` for an unknown job. When the job is already terminal the
        queue is ``None`` and the terminal status is returned so the caller can
        replay, send ``__status`` and close.
        """
        with self._lock:
            record = self._records.get(job_id)
            if record is not None:
                replayed = [event.model_dump() for event in record.job.events]
                if record.job.status in TERMINAL:
                    return replayed, None, record.job.status
                queue: asyncio.Queue = asyncio.Queue()
                record.subscribers.append((loop, queue))
                return replayed, queue, None
        # Not live: a persisted terminal job replays from disk, otherwise unknown.
        job = self._find_on_disk(job_id)
        if job is None:
            return None
        return [event.model_dump() for event in job.events], None, job.status

    def unsubscribe(self, job_id: str, queue: asyncio.Queue | None) -> None:
        if queue is None:
            return
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                return
            record.subscribers = [sub for sub in record.subscribers if sub[1] is not queue]

    # -- runner ------------------------------------------------------------
    def start(self, project_id: str, stage: str, options: dict[str, Any]) -> Job:
        job = self.create(project_id, stage)
        record = self._records[job.id]
        record.thread = threading.Thread(
            target=self._run, args=(record, project_id, dict(options or {})),
            name=f"clipper-job-{job.id[:8]}", daemon=True,
        )
        record.thread.start()
        return job

    def _run(self, record: _Record, project_id: str, options: dict[str, Any]) -> None:
        job = record.job
        job.status = "running"
        _persist(job)
        status = "done"
        source = projects.resolve_source(project_id)

        def emit(**kw: Any) -> None:
            self.add_event(
                job.id,
                JobEvent(
                    type=str(kw.get("type") or "log"),
                    node=kw.get("node"),
                    pct=kw.get("pct"),
                    message=str(kw.get("message") or ""),
                    level=str(kw.get("level") or "info"),
                    ts=time.time(),
                    cached=bool(kw.get("cached", False)),
                ),
            )

        emit(type="log", message=f"{job.stage} started", level="info")
        try:
            if job.stage == "analysis":
                graph = analysis_graph(
                    project_id,
                    source,
                    n_clips=int(options.get("n_clips", 8)),
                    min_duration=int(options.get("min_duration", 15)),
                    max_duration=int(options.get("max_duration", 60)),
                    cookies_from_browser=options.get("cookies")
                    or projects.read_manifest(project_id).get("cookies"),
                )
                results, _ctx = run_graph(
                    graph, project_id, emit=emit, cancel=record.cancel
                )
                job.result = results.get("export", {})
            else:
                graph = render_graph(
                    project_id,
                    source,
                    clips_path=options.get("clips_path"),
                    clips_inline=options.get("clips_inline"),
                    caption_style=options.get("caption_style"),
                    reframe=options.get("reframe") or "auto",
                    lut=options.get("lut"),
                    music=options.get("music"),
                    platform=options.get("platform") or "shorts",
                    add_titles=bool(options.get("add_titles", True)),
                    track_subjects=bool(options.get("track", True)),
                    cookies_from_browser=options.get("cookies")
                    or projects.read_manifest(project_id).get("cookies"),
                )
                results, _ctx = run_graph(
                    graph, project_id, emit=emit, cancel=record.cancel
                )
                render_result = results.get("render", {}) or {}
                metadata_result = results.get("metadata", {}) or {}
                job.result = {
                    "renders": render_result.get("renders", []),
                    "metadata_file": metadata_result.get("metadata_file"),
                }

            if record.cancel.is_set():
                status = "cancelled"
        except Cancelled:
            status = "cancelled"
        except Exception as exc:  # noqa: BLE001 - surfaced to the client verbatim
            status = "error"
            job.error = str(exc)
            self.add_event(
                job.id,
                JobEvent(type="error", message=str(exc), level="error", ts=time.time()),
            )
        finally:
            self._finish(job.id, status)

    def _finish(self, job_id: str, status: str) -> None:
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                return
            record.job.status = status  # type: ignore[assignment]
            subscribers = list(record.subscribers)
            record.subscribers.clear()
        _persist(record.job)
        _dispatch(subscribers, {"type": "__status", "status": status})


def _dispatch(
    subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]],
    message: dict[str, Any],
) -> None:
    for loop, queue in subscribers:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, message)
        except RuntimeError:
            continue


# The single process-wide registry.
REGISTRY = JobRegistry()

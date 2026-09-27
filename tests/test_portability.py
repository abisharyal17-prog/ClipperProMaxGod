"""Project export/import and persisted job history.

Both features keep a user's work on *their* machine across browser and engine
restarts, so their isolation is complete: export/import moves data between
installs, and job history is written to ``data/projects/<id>/jobs/``.
"""

from __future__ import annotations

import asyncio
import json
import zipfile

import pytest

from app import paths
from app.api import jobs, projects
from app.api.schemas import JobEvent


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the project store at a throwaway directory."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths, "PROJECTS", projects_dir)
    monkeypatch.setattr(projects, "PROJECTS", projects_dir)
    monkeypatch.setattr(projects, "EXPORTS_DIR", tmp_path / "exports")
    return tmp_path


def _make_project(project_id: str = "demo") -> str:
    projects.create_project(project_id, "https://example.com/v", title="Demo")
    root = projects.project_dir(project_id)
    (root / "transcript").mkdir(parents=True, exist_ok=True)
    (root / "transcript" / "transcript.txt").write_text("hello", encoding="utf-8")
    (root / "clips").mkdir(parents=True, exist_ok=True)
    (root / "clips" / "clips.json").write_text(
        json.dumps({"defaults": {}, "clips": [{"id": "clip_001", "start": 0, "end": 5}]}),
        encoding="utf-8",
    )
    return project_id


# --- export / import ------------------------------------------------------
def test_export_import_round_trip(store):
    pid = _make_project("alpha")
    archive = projects.export_archive(pid)
    assert archive.is_file() and archive.suffix == ".zip"

    new_id = projects.import_archive(archive)
    assert new_id != pid or projects.exists(new_id)
    assert projects.exists(new_id)
    assert projects.read_manifest(new_id)["id"] == new_id
    restored = projects.project_dir(new_id) / "transcript" / "transcript.txt"
    assert restored.read_text(encoding="utf-8") == "hello"
    assert projects.detail(new_id)["summary"]["has_clips"] is True


def test_export_excludes_cache(store):
    pid = _make_project("cached")
    cache = projects.project_dir(pid) / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "big.bin").write_bytes(b"x" * 1000)

    archive = projects.export_archive(pid)
    with zipfile.ZipFile(archive) as zipped:
        assert not any(name.startswith("cache/") for name in zipped.namelist())


def test_import_twice_gets_unique_ids(store):
    pid = _make_project("dup")
    archive = projects.export_archive(pid)
    first = projects.import_archive(archive)
    second = projects.import_archive(archive)
    assert first != second
    assert projects.exists(first) and projects.exists(second)


def test_import_rejects_non_project_archive(store):
    bad = store / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zipped:
        zipped.writestr("readme.txt", "nope")
    with pytest.raises(ValueError):
        projects.import_archive(bad)


def test_import_rejects_zip_slip(store):
    bad = store / "evil.zip"
    with zipfile.ZipFile(bad, "w") as zipped:
        zipped.writestr("project.json", json.dumps({"id": "evil"}))
        zipped.writestr("../escape.txt", "pwned")
    with pytest.raises(ValueError):
        projects.import_archive(bad)
    assert not (store / "escape.txt").exists()


# --- persisted job history ------------------------------------------------
def test_job_is_persisted_on_create(store):
    pid = _make_project("jobsdemo")
    registry = jobs.JobRegistry()
    job = registry.create(pid, "analysis")
    assert (projects.project_dir(pid) / "jobs" / f"{job.id}.json").is_file()


def test_job_history_survives_restart(store):
    pid = _make_project("restart")
    registry = jobs.JobRegistry()
    job = registry.create(pid, "analysis")

    restarted = jobs.JobRegistry()  # no in-memory state
    assert restarted.get(job.id) is not None
    assert any(j.id == job.id for j in restarted.list_for_project(pid))


def test_interrupted_job_is_marked_error(store):
    pid = _make_project("stale")
    registry = jobs.JobRegistry()
    job = registry.create(pid, "analysis")
    job.status = "running"
    jobs._persist(job)

    reloaded = jobs.JobRegistry().get(job.id)
    assert reloaded is not None
    assert reloaded.status == "error"
    assert "restarted" in (reloaded.error or "")


def test_completed_job_keeps_status_and_result(store):
    pid = _make_project("finished")
    registry = jobs.JobRegistry()
    job = registry.create(pid, "render")
    registry._finish(job.id, "done")

    reloaded = jobs.JobRegistry().get(job.id)
    assert reloaded is not None
    assert reloaded.status == "done"


def test_subscribe_replays_persisted_job(store):
    pid = _make_project("sub")
    registry = jobs.JobRegistry()
    job = registry.create(pid, "analysis")
    registry.add_event(job.id, JobEvent(type="log", message="hi", ts=1.0))
    jobs._persist(registry.get(job.id))

    replayed, queue, status = jobs.JobRegistry().subscribe(job.id, asyncio.new_event_loop())
    assert queue is None
    assert status in {"error", "done", "cancelled"}
    assert any(event["message"] == "hi" for event in replayed)


# --- API surface ----------------------------------------------------------
def test_export_then_import_over_http(store, monkeypatch):
    monkeypatch.setenv("CLIPPER_AUTH", "0")
    from fastapi.testclient import TestClient

    from app.api.server import app

    client = TestClient(app)
    pid = _make_project("apiexp")

    export = client.get(f"/api/projects/{pid}/export")
    assert export.status_code == 200
    assert export.headers["content-type"] == "application/zip"

    imported = client.post(
        "/api/projects/import",
        files={"file": ("apiexp.zip", export.content, "application/zip")},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["id"]
    assert body["has_clips"] is True


def test_import_api_rejects_garbage(store, monkeypatch):
    monkeypatch.setenv("CLIPPER_AUTH", "0")
    from fastapi.testclient import TestClient

    from app.api.server import app

    client = TestClient(app)
    response = client.post(
        "/api/projects/import",
        files={"file": ("bad.zip", b"not a zip", "application/zip")},
    )
    assert response.status_code == 400


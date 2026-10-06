"""Startup recovery acceptance tests (Phase 7, scenarios A/B).

Simulates crash/power-loss by seeding durable rows in live states plus
partial artifacts, then running the reconciler the same way the lifespan
does before the scheduler starts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_media_downloader import jobs
from local_media_downloader.db import initialize
from local_media_downloader.job_state import JobState
from local_media_downloader.services.events import EventBus
from local_media_downloader.services.recovery import recover_interrupted_jobs


def _plan() -> str:
    return json.dumps(
        {
            "strategy": "copy",
            "steps": [{"kind": "SELECT_FORMAT", "tool": "yt_dlp", "detail": {"selector": "best"}}],
        }
    )


@pytest.fixture
def env(tmp_path):
    conn = initialize(tmp_path / "app.db")
    return conn, tmp_path


def _seed(conn, state: JobState, tmp_path: Path, *, with_plan: bool = True) -> jobs.Job:
    job = jobs.create_job(
        conn,
        source_url="https://example.com/v",
        execution_plan_json=_plan() if with_plan else None,
        state=JobState.QUEUED,
    )
    # Move directly into the target live state without going through the
    # executor: the whole point is that the worker is gone.
    if state is not JobState.QUEUED:
        conn.execute("UPDATE jobs SET state = ? WHERE id = ?", (state.value, job.id))
    updated = jobs.get_job(conn, job.id)
    assert updated is not None
    return updated


def _partials(tmp_path: Path, job_id: str) -> Path:
    job_dir = tmp_path / "jobs" / job_id
    for sub in ("source", "work"):
        d = job_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "partial.mp4").write_bytes(b"junk")
    return job_dir


def test_downloading_job_is_requeued_and_partials_cleaned(env):
    conn, tmp_path = env
    job = _seed(conn, JobState.DOWNLOADING, tmp_path)
    job_dir = _partials(tmp_path, job.id)

    report = recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3, bus=None)

    updated = jobs.get_job(conn, job.id)
    assert updated is not None
    assert updated.state is JobState.QUEUED
    assert updated.error_code == "INTERRUPTED"
    assert updated.attempt_count == 1
    assert not (job_dir / "source" / "partial.mp4").exists()
    assert not (job_dir / "work" / "partial.mp4").exists()
    assert report.actions and report.actions[0].to_state == "QUEUED"


def test_committing_with_output_on_disk_goes_to_recovery_required(env):
    conn, tmp_path = env
    job = _seed(conn, JobState.COMMITTING, tmp_path)
    job_dir = tmp_path / "jobs" / job.id
    out = job_dir / "output"
    out.mkdir(parents=True)
    (out / "video.mp4").write_bytes(b"maybe-final")

    recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3)

    updated = jobs.get_job(conn, job.id)
    assert updated is not None
    assert updated.state is JobState.RECOVERY_REQUIRED
    assert updated.error_code == "INTERRUPTED"
    assert (out / "video.mp4").exists(), "never delete/overwrite a possibly-final file"


def test_crash_loop_gives_up_with_failed(env):
    conn, tmp_path = env
    job = _seed(conn, JobState.DOWNLOADING, tmp_path)
    with conn:
        conn.execute("UPDATE jobs SET attempt_count = 2 WHERE id = ?", (job.id,))

    recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3)

    updated = jobs.get_job(conn, job.id)
    assert updated is not None
    assert updated.state is JobState.FAILED
    assert updated.error_code == "INTERRUPTED"


def test_cancel_requested_with_dead_worker_becomes_cancelled(env):
    conn, tmp_path = env
    job = _seed(conn, JobState.CANCEL_REQUESTED, tmp_path)

    recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3)

    checked = jobs.get_job(conn, job.id)
    assert checked is not None
    assert checked.state is JobState.CANCELLED


def test_orphaned_retry_wait_is_rewoken(env):
    conn, tmp_path = env
    job = _seed(conn, JobState.RETRY_WAIT, tmp_path)

    recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3)

    checked = jobs.get_job(conn, job.id)
    assert checked is not None
    assert checked.state is JobState.QUEUED


def test_job_without_plan_goes_to_recovery_required(env):
    conn, tmp_path = env
    job = _seed(conn, JobState.PROCESSING, tmp_path, with_plan=False)

    recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3)

    checked = jobs.get_job(conn, job.id)
    assert checked is not None
    assert checked.state is JobState.RECOVERY_REQUIRED


def test_completed_job_output_is_never_touched(env):
    conn, tmp_path = env
    job = jobs.create_job(
        conn,
        source_url="https://example.com/v",
        execution_plan_json=_plan(),
        state=JobState.COMMITTING,
    )
    out = tmp_path / "jobs" / job.id / "output"
    out.mkdir(parents=True)
    final = out / "done.mp4"
    final.write_bytes(b"final")
    jobs.set_output_path(conn, job.id, str(final))
    jobs.transition(conn, job.id, JobState.COMPLETED, current_stage="completed", progress=1.0)

    recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3)

    checked = jobs.get_job(conn, job.id)
    assert checked is not None
    assert checked.state is JobState.COMPLETED
    assert final.exists()


def test_recovery_writes_audit_log(env):
    conn, tmp_path = env
    job = _seed(conn, JobState.DOWNLOADING, tmp_path)
    _partials(tmp_path, job.id)

    recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3)

    log = tmp_path / "jobs" / job.id / "logs" / "recovery.log"
    assert log.exists()
    assert "requeued" in log.read_text()


def test_bus_receives_recovery_events(env):
    conn, tmp_path = env
    _seed(conn, JobState.DOWNLOADING, tmp_path)
    bus = EventBus()

    recover_interrupted_jobs(conn, data_dir=tmp_path, max_attempts=3, bus=bus)

    assert any(e.kind == "state" and e.payload.get("reason") == "requeued" for e in bus.history)

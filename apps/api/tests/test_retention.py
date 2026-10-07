from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from local_media_downloader.db import initialize
from local_media_downloader.job_state import JobState
from local_media_downloader.jobs import create_job, transition
from local_media_downloader.services.retention import RetentionPolicy, run_retention


@pytest.fixture
def conn(tmp_path):
    connection = initialize(tmp_path / "app.db")
    try:
        yield connection
    finally:
        connection.close()


def _old_terminal_job(conn, *, url: str = "https://example.com/v", days_old: int = 10):
    job = create_job(conn, source_url=url, state=JobState.QUEUED)
    transition(conn, job.id, JobState.DOWNLOADING)
    transition(conn, job.id, JobState.FAILED, error_code="NETWORK_ERROR")
    old = (datetime.now(UTC) - timedelta(days=days_old)).isoformat(timespec="milliseconds")
    conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (old, job.id))
    conn.commit()
    return job


def test_retention_redacts_source_url_for_old_terminal_jobs(conn, tmp_path) -> None:
    job = _old_terminal_job(conn, days_old=10)
    policy = RetentionPolicy(source_url_retention="7days")
    report = run_retention(conn, data_dir=tmp_path, policy=policy)
    assert report.urls_redacted == 1
    from local_media_downloader.jobs import get_job

    updated = get_job(conn, job.id)
    assert updated is not None
    assert updated.source_url is None
    assert updated.source_url_hash is not None


def test_retention_never_redacts_when_policy_is_never(conn, tmp_path) -> None:
    _old_terminal_job(conn, days_old=365)
    policy = RetentionPolicy(source_url_retention="never")
    report = run_retention(conn, data_dir=tmp_path, policy=policy)
    assert report.urls_redacted == 0


def test_retention_deletes_old_history_rows(conn, tmp_path) -> None:
    job = _old_terminal_job(conn, days_old=40)
    policy = RetentionPolicy(history_retention_days=30)
    report = run_retention(conn, data_dir=tmp_path, policy=policy)
    assert report.jobs_deleted == 1
    from local_media_downloader.jobs import get_job

    assert get_job(conn, job.id) is None


def test_retention_keeps_recent_history(conn, tmp_path) -> None:
    _old_terminal_job(conn, days_old=5)
    policy = RetentionPolicy(history_retention_days=30)
    report = run_retention(conn, data_dir=tmp_path, policy=policy)
    assert report.jobs_deleted == 0


def test_retention_deletes_old_job_directories(conn, tmp_path) -> None:
    job = _old_terminal_job(conn, days_old=2)
    job_dir = tmp_path / "jobs" / job.id / "source"
    job_dir.mkdir(parents=True)
    (job_dir / "partial.mp4").write_text("data")
    policy = RetentionPolicy(temporary_retention_hours=1)
    report = run_retention(conn, data_dir=tmp_path, policy=policy)
    assert report.directories_deleted == 1
    assert not (tmp_path / "jobs" / job.id).exists()


def test_retention_never_touches_active_jobs(conn, tmp_path) -> None:
    job = create_job(conn, source_url="https://example.com/active", state=JobState.QUEUED)
    policy = RetentionPolicy(
        source_url_retention="immediately", history_retention_days=0, temporary_retention_hours=0
    )
    report = run_retention(conn, data_dir=tmp_path, policy=policy)
    assert report.urls_redacted == 0
    assert report.jobs_deleted == 0
    from local_media_downloader.jobs import get_job

    assert get_job(conn, job.id) is not None


def test_retention_policy_validates_options() -> None:
    with pytest.raises(ValueError):
        RetentionPolicy(source_url_retention="sometimes")
    with pytest.raises(ValueError):
        RetentionPolicy(history_retention_days=-1)

"""Retention and cleanup policies (Phase 12).

Three independent clocks, all measured from a job's ``updated_at`` — the last
state change, which for a terminal job is when it became terminal:

- ``source_url_retention`` — how long the full URL is kept before being replaced
  by NULL + its SHA-256 hash. The hash is what dedupe and audit need; the URL
  itself is not worth keeping forever.
- ``temporary_retention_hours`` — how long a finished job's temporary artifacts
  (``source/``, ``work/``, ``logs/``) survive. Final output lives in the output
  root, never here, so deleting a job directory never deletes user media.
- ``history_retention_days`` — how long a terminal job stays in history before
  its row is deleted.

Cleanup never blocks job state transitions (TECHNICAL_SPEC §9): every step is
best-effort, records its own failures, and a failure here must not stop the
scheduler.
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .. import jobs
from ..job_state import TERMINAL_STATES, JobState
from .events import EventBus, StreamEvent

# How often the periodic sweep runs. Retention is measured in hours/days, so a
# daily sweep is granularity enough and keeps the cost near zero.
_SWEEP_INTERVAL = timedelta(hours=6)

URL_RETENTION_OPTIONS = ("immediately", "7days", "30days", "never")
DEFAULT_URL_RETENTION = "7days"
DEFAULT_HISTORY_RETENTION_DAYS = 30
DEFAULT_TEMPORARY_RETENTION_HOURS = 24


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    source_url_retention: str = DEFAULT_URL_RETENTION
    history_retention_days: int = DEFAULT_HISTORY_RETENTION_DAYS
    temporary_retention_hours: int = DEFAULT_TEMPORARY_RETENTION_HOURS

    def __post_init__(self) -> None:
        if self.source_url_retention not in URL_RETENTION_OPTIONS:
            raise ValueError(
                f"source_url_retention must be one of {URL_RETENTION_OPTIONS}, "
                f"got {self.source_url_retention!r}"
            )
        if self.history_retention_days < 0:
            raise ValueError("history_retention_days must be >= 0")
        if self.temporary_retention_hours < 0:
            raise ValueError("temporary_retention_hours must be >= 0")

    @property
    def url_retention_days(self) -> int | None:
        if self.source_url_retention == "immediately":
            return 0
        if self.source_url_retention == "never":
            return None
        return int(self.source_url_retention.removesuffix("days"))


@dataclass(slots=True)
class RetentionReport:
    urls_redacted: int = 0
    jobs_deleted: int = 0
    directories_deleted: int = 0
    errors: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)


def run_retention(
    conn: sqlite3.Connection,
    *,
    data_dir: Path,
    policy: RetentionPolicy,
    bus: EventBus | None = None,
    now: datetime | None = None,
) -> RetentionReport:
    """Apply the retention policy. Safe to call repeatedly; idempotent."""
    report = RetentionReport()
    moment = now or datetime.now(UTC)
    url_days = policy.url_retention_days

    if url_days is not None:
        cutoff = (moment - timedelta(days=url_days)).isoformat(timespec="milliseconds")
        for job in jobs.list_terminal_older_than(conn, cutoff):
            if job.source_url is None:
                continue
            try:
                jobs.clear_source_url(conn, job.id)
                report.urls_redacted += 1
            except Exception as error:
                report.add_error(f"redact {job.id}: {error}")

    temp_cutoff = (moment - timedelta(hours=policy.temporary_retention_hours)).isoformat(
        timespec="milliseconds"
    )
    for job in jobs.list_terminal_older_than(conn, temp_cutoff):
        deleted = _delete_job_dir(data_dir, job.id)
        if deleted:
            report.directories_deleted += 1

    history_cutoff = (moment - timedelta(days=policy.history_retention_days)).isoformat(
        timespec="milliseconds"
    )
    for job in jobs.list_terminal_older_than(conn, history_cutoff):
        try:
            if jobs.delete_job(conn, job.id):
                report.jobs_deleted += 1
        except Exception as error:
            report.add_error(f"delete {job.id}: {error}")

    _delete_orphan_dirs(data_dir, temp_cutoff, report)
    _notify(bus, report)
    return report


def _delete_job_dir(data_dir: Path, job_id: str) -> bool:
    directory = data_dir / "jobs" / job_id
    if not directory.exists():
        return False
    shutil.rmtree(directory, ignore_errors=True)
    return not directory.exists()


def _delete_orphan_dirs(data_dir: Path, cutoff: str, report: RetentionReport) -> None:
    """Delete job directories whose row is gone and whose mtime predates ``cutoff``.

    A directory with no job row is by definition temporary: final output lives in
    the output root, so anything left in ``data/jobs/`` is an artifact.
    """
    jobs_root = data_dir / "jobs"
    if not jobs_root.is_dir():
        return
    for child in jobs_root.iterdir():
        if not child.is_dir():
            continue
        try:
            mtime = datetime.fromtimestamp(child.stat().st_mtime, UTC).isoformat(
                timespec="milliseconds"
            )
        except OSError:
            continue
        if mtime >= cutoff:
            continue
        shutil.rmtree(child, ignore_errors=True)
        if not child.exists():
            report.directories_deleted += 1


def _notify(bus: EventBus | None, report: RetentionReport) -> None:
    if bus is None or (
        report.urls_redacted == 0 and report.jobs_deleted == 0 and report.directories_deleted == 0
    ):
        return
    bus.publish(
        StreamEvent(
            kind="maintenance",
            job_id=None,
            payload={
                "event": "retention_sweep",
                "urls_redacted": report.urls_redacted,
                "jobs_deleted": report.jobs_deleted,
                "directories_deleted": report.directories_deleted,
                "errors": len(report.errors),
            },
        )
    )


async def retention_sweep_loop(
    conn: sqlite3.Connection,
    *,
    data_dir: Path,
    policy: RetentionPolicy,
    bus: EventBus | None = None,
) -> None:
    """Run :func:`run_retention` every ``_SWEEP_INTERVAL`` until cancelled."""
    import asyncio

    while True:
        with suppress(Exception):
            run_retention(conn, data_dir=data_dir, policy=policy, bus=bus)
        await asyncio.sleep(_SWEEP_INTERVAL.total_seconds())


def terminal_states() -> frozenset[JobState]:
    return TERMINAL_STATES

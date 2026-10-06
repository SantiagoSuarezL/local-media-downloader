"""Startup recovery: reconcile Durable state against reality.

Runs once, after the database is opened and before the scheduler starts.
Any job still in a live/executing state (ACTIVE_STATES) or waiting for a
cancel acknowledgement has no live worker anymore — the process that owned
it died (crash, power loss) or never existed in this boot. Recovery makes
that explicit instead of letting the row masquerade as in-progress forever
(TECHNICAL_SPEC §12-13, ARCHITECTURE §5).

Policy per job:

- ``CANCEL_REQUESTED`` → ``CANCELLED``: the worker that would have
  acknowledged it is gone; the request is durable, so the outcome is too.
- Active job, unambiguous and retry-budgeted → ``RETRY_WAIT`` then
  ``QUEUED``: safe to restart because nothing was committed to ``output/``
  (the executor only moves a file there after validation). Partial
  ``source/``/``work/`` artifacts are deleted, never promoted.
- Active job in ``COMMITTING`` with a final file on disk → ambiguous:
  we cannot know whether the rename finished before the crash, so the
  output is kept and the job goes to ``RECOVERY_REQUIRED`` for manual
  review. A completed final file is NEVER silently overwritten or deleted.
- Attempt budget exhausted (crash-loop protection) or no execution plan →
  ``FAILED`` / ``RECOVERY_REQUIRED`` respectively.
- Orphaned ``RETRY_WAIT`` (backoff sleep died with the process) →
  ``QUEUED`` while attempts remain, else ``FAILED``.

There is no INTERRUPTED job state on purpose: the durable signal is
``error_code="INTERRUPTED"`` on the audit event plus the state itself.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .. import jobs
from ..job_state import ACTIVE_STATES, JobState
from .events import EventBus, StreamEvent

_INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True, slots=True)
class RecoveryAction:
    job_id: str
    from_state: str
    to_state: str
    reason: str


@dataclass(slots=True)
class RecoveryReport:
    actions: list[RecoveryAction] = field(default_factory=list)

    def add(self, job_id: str, from_state: str, to_state: str, reason: str) -> None:
        self.actions.append(RecoveryAction(job_id, from_state, to_state, reason))


def recover_interrupted_jobs(
    conn: sqlite3.Connection,
    *,
    data_dir: Path,
    max_attempts: int,
    bus: EventBus | None = None,
) -> RecoveryReport:
    report = RecoveryReport()

    for job in jobs.list_jobs(conn, states={JobState.CANCEL_REQUESTED}):
        jobs.transition(conn, job.id, JobState.CANCELLED, error_code=_INTERRUPTED)
        report.add(
            job.id, job.state.value, JobState.CANCELLED.value, "cancel acknowledged by dead worker"
        )
        _notify(bus, job.id, JobState.CANCELLED, "cancel_acknowledged")

    for job in jobs.list_jobs(conn, states=set(ACTIVE_STATES)):
        job_dir = data_dir / "jobs" / job.id
        attempts = jobs.increment_attempts(conn, job.id)

        final_present = job.output_path is not None and Path(job.output_path).exists()
        output_dir = job_dir / "output"
        ambiguous_commit = (
            job.state is JobState.COMMITTING and output_dir.exists() and any(output_dir.iterdir())
        ) or (job.state is JobState.COMMITTING and final_present)

        if ambiguous_commit:
            jobs.transition(
                conn,
                job.id,
                JobState.RECOVERY_REQUIRED,
                error_code=_INTERRUPTED,
                error_message="Interrupted while finalizing; output kept for review.",
            )
            report.add(
                job.id, job.state.value, JobState.RECOVERY_REQUIRED.value, "ambiguous commit"
            )
            _notify(bus, job.id, JobState.RECOVERY_REQUIRED, "ambiguous_commit")
            _log_recovery(job_dir, "recovery_required", "ambiguous committing state")
            continue

        _clean_partials(job_dir)

        if job.execution_plan_json is None:
            jobs.transition(
                conn,
                job.id,
                JobState.RECOVERY_REQUIRED,
                error_code=_INTERRUPTED,
                error_message="Interrupted and missing its execution plan.",
            )
            report.add(
                job.id, job.state.value, JobState.RECOVERY_REQUIRED.value, "no execution plan"
            )
            _notify(bus, job.id, JobState.RECOVERY_REQUIRED, "no_plan")
            _log_recovery(job_dir, "recovery_required", "missing execution plan")
            continue

        if attempts >= max_attempts:
            jobs.transition(
                conn,
                job.id,
                JobState.FAILED,
                error_code=_INTERRUPTED,
                error_message=f"Interrupted {attempts} time(s); giving up to avoid a crash loop.",
            )
            report.add(job.id, job.state.value, JobState.FAILED.value, "attempt budget exhausted")
            _notify(bus, job.id, JobState.FAILED, "attempt_budget_exhausted")
            _log_recovery(job_dir, "failed", f"attempts={attempts} >= {max_attempts}")
            continue

        try:
            jobs.transition(
                conn,
                job.id,
                JobState.RETRY_WAIT,
                error_code=_INTERRUPTED,
                error_message="Interrupted by a restart; will retry.",
            )
            jobs.transition(conn, job.id, JobState.QUEUED)
        except Exception:
            jobs.transition(
                conn,
                job.id,
                JobState.FAILED,
                error_code=_INTERRUPTED,
                error_message="Recovery failed.",
            )
            report.add(
                job.id, job.state.value, JobState.FAILED.value, "illegal recovery transition"
            )
            _log_recovery(job_dir, "failed", "illegal transition")
            continue
        report.add(job.id, job.state.value, JobState.QUEUED.value, "requeued after interruption")
        _notify(bus, job.id, JobState.QUEUED, "requeued")
        _log_recovery(job_dir, "requeued", f"attempts={attempts}")

    for job in jobs.list_jobs(conn, states={JobState.RETRY_WAIT}):
        attempts = job.attempt_count
        if attempts >= max_attempts:
            try:
                jobs.transition(
                    conn,
                    job.id,
                    JobState.FAILED,
                    error_code=job.error_code or _INTERRUPTED,
                    error_message=job.error_message or "Retry budget exhausted during recovery.",
                )
                report.add(job.id, job.state.value, JobState.FAILED.value, "retry budget exhausted")
                _notify(bus, job.id, JobState.FAILED, "attempt_budget_exhausted")
            except Exception:
                pass
            continue
        try:
            jobs.transition(conn, job.id, JobState.QUEUED)
            report.add(job.id, job.state.value, JobState.QUEUED.value, "orphaned retry rewoken")
            _notify(bus, job.id, JobState.QUEUED, "retry_revived")
        except Exception:
            pass

    return report


def _clean_partials(job_dir: Path) -> None:
    """Delete partial source/work/output artifacts; never touch COMPLETED jobs."""
    for sub in ("source", "work", "output"):
        directory = job_dir / sub
        if directory.exists():
            for child in directory.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)


def _notify(bus: EventBus | None, job_id: str, state: JobState, reason: str) -> None:
    if bus is None:
        return
    bus.publish(
        StreamEvent(
            kind="state",
            job_id=job_id,
            payload={"job_id": job_id, "state": state.value, "reason": reason},
        )
    )


def _log_recovery(job_dir: Path, outcome: str, detail: str) -> None:
    try:
        logs = job_dir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "outcome": outcome,
                "detail": detail,
            }
        )
        with (logs / "recovery.log").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass

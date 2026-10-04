"""Job repository: the only writer of job state.

Every state transition is validated by the state machine, written to the jobs
row, and paired with a job_events audit record inside a single transaction.
Event payloads never contain the full source URL — only its SHA-256 hash
(TECHNICAL_SPEC §9).
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from .db import transaction
from .job_state import ACTIVE_STATES, JobState, assert_transition


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    created_at: str
    updated_at: str
    state: JobState
    source_url_hash: str
    source_url: str | None
    extractor: str | None
    title: str | None
    progress: float
    bytes_downloaded: int
    total_bytes: int | None
    current_stage: str | None
    attempt_count: int
    error_code: str | None
    error_message: str | None
    output_path: str | None
    created_by: str | None
    priority: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Job:
        return cls(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            state=JobState(row["state"]),
            source_url_hash=row["source_url_hash"],
            source_url=row["source_url"],
            extractor=row["extractor"],
            title=row["title"],
            progress=row["progress"],
            bytes_downloaded=row["bytes_downloaded"],
            total_bytes=row["total_bytes"],
            current_stage=row["current_stage"],
            attempt_count=row["attempt_count"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            output_path=row["output_path"],
            created_by=row["created_by"],
            priority=row["priority"],
        )


def create_job(
    conn: sqlite3.Connection,
    *,
    source_url: str,
    created_by: str = "ui",
    title: str | None = None,
    priority: int = 0,
) -> Job:
    job_id = str(uuid.uuid4())
    now = _now()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO jobs (id, created_at, updated_at, state, source_url, source_url_hash,
                              title, created_by, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                now,
                now,
                JobState.CREATED.value,
                source_url,
                hash_url(source_url),
                title,
                created_by,
                priority,
            ),
        )
        _record_event(conn, job_id, "JOB_CREATED", {"created_by": created_by})
    job = get_job(conn, job_id)
    if job is None:  # pragma: no cover — insert just happened
        raise RuntimeError("job vanished after insert")
    return job


def get_job(conn: sqlite3.Connection, job_id: str) -> Job | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return Job.from_row(row) if row else None


def list_jobs(
    conn: sqlite3.Connection,
    *,
    states: set[JobState] | None = None,
    limit: int = 100,
) -> list[Job]:
    if states:
        placeholders = ",".join("?" for _ in states)
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE state IN ({placeholders})"
            " ORDER BY priority DESC, created_at LIMIT ?",
            (*(s.value for s in states), limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY priority DESC, created_at LIMIT ?", (limit,)
        ).fetchall()
    return [Job.from_row(r) for r in rows]


def _record_event(
    conn: sqlite3.Connection,
    job_id: str,
    event_type: str,
    payload: dict[str, object] | None = None,
) -> None:
    import json

    conn.execute(
        "INSERT INTO job_events (job_id, timestamp, event_type, payload_json) VALUES (?, ?, ?, ?)",
        (job_id, _now(), event_type, json.dumps(payload) if payload else None),
    )


def transition(
    conn: sqlite3.Connection,
    job_id: str,
    target: JobState,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    current_stage: str | None = None,
    progress: float | None = None,
) -> Job:
    job = get_job(conn, job_id)
    if job is None:
        raise KeyError(job_id)
    assert_transition(job.state, target)

    now = _now()
    with transaction(conn):
        conn.execute(
            """
            UPDATE jobs
               SET state = ?, updated_at = ?,
                   error_code = COALESCE(?, error_code),
                   error_message = COALESCE(?, error_message),
                   current_stage = COALESCE(?, current_stage),
                   progress = COALESCE(?, progress)
             WHERE id = ?
            """,
            (target.value, now, error_code, error_message, current_stage, progress, job_id),
        )
        payload: dict[str, object] = {"from": job.state.value, "to": target.value}
        if error_code:
            payload["error_code"] = error_code
        _record_event(conn, job_id, "STATE_CHANGED", payload)

    updated = get_job(conn, job_id)
    if updated is None:  # pragma: no cover
        raise RuntimeError("job vanished after transition")
    return updated


def find_active_jobs(conn: sqlite3.Connection) -> list[Job]:
    """Jobs found in a live/executing state at startup.

    These may have lost their worker process (crash, power loss). The recovery
    subsystem reconciles them; the repository only reports them (ARCHITECTURE §5).
    """
    return list_jobs(conn, states=set(ACTIVE_STATES))


def get_events(conn: sqlite3.Connection, job_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()

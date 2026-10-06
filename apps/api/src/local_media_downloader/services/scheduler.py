"""Asyncio scheduler with a durable queue in SQLite.

The jobs row is the source of truth; the scheduler only ever reads QUEUED
rows (priority DESC, created_at ASC, id) and transitions them. Limits are
configurable and bounded so ten submitted jobs never produce ten ffmpeg
processes (the Phase 6 acceptance criterion).

- ``max_active``: jobs with a live worker at once (default 3).
- ``max_downloads``: concurrent yt-dlp downloads (default 2), enforced by a
  semaphore owned by the executor.
- ``max_encoders``: concurrent ffmpeg processes (default 1), same.

Cancellation is cooperative: a cancel request sets an asyncio.Event and the
worker observes it between stages; a queued job is marked CANCELLED
immediately. Retries are bounded with backoff and driven through RETRY_WAIT.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol

from .. import jobs
from ..domain.errors import ErrorCode, ExtractionError
from ..domain.plan import ExecutionPlan, PlanStep
from ..job_state import ACTIVE_STATES, JobState
from .events import EventBus, StreamEvent
from .executor import JobCancelled

_MIN_DISK_FREE_BYTES = 512 * 1024**2


@dataclass(frozen=True, slots=True)
class SchedulerLimits:
    max_active: int = 3
    max_downloads: int = 2
    max_encoders: int = 1
    max_attempts: int = 3
    retry_backoff_seconds: float = 2.0


class ExecutorProtocol(Protocol):
    async def run(self, job: jobs.Job, plan: ExecutionPlan, cancel: asyncio.Event) -> object: ...


class Scheduler:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        executor: ExecutorProtocol,
        bus: EventBus,
        limits: SchedulerLimits | None = None,
        working_dir: str = "data",
    ) -> None:
        self._conn = conn
        self._executor = executor
        self._bus = bus
        self._limits = limits or SchedulerLimits()
        self._working_dir = working_dir
        self._wake = asyncio.Event()
        self._cancels: dict[str, asyncio.Event] = {}
        self._active: dict[str, asyncio.Task[None]] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def limits(self) -> SchedulerLimits:
        return self._limits

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="scheduler")

    async def stop(self) -> None:
        self._running = False
        self._wake.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        for cancel in self._cancels.values():
            cancel.set()
        for task in list(self._active.values()):
            task.cancel()
        if self._active:
            await asyncio.gather(*self._active.values(), return_exceptions=True)

    def wake(self) -> None:
        self._wake.set()

    def request_cancel(self, job_id: str) -> None:
        job = jobs.get_job(self._conn, job_id)
        if job is None:
            raise KeyError(job_id)
        if job.state is JobState.QUEUED or job.state is JobState.RETRY_WAIT:
            jobs.transition(self._conn, job_id, JobState.CANCELLED)
            self._bus.publish(
                StreamEvent(
                    kind="state", job_id=job_id, payload={"job_id": job_id, "state": "CANCELLED"}
                )
            )
            return
        if job.state in ACTIVE_STATES or job.state is JobState.CANCEL_REQUESTED:
            try:
                jobs.transition(self._conn, job_id, JobState.CANCEL_REQUESTED)
                reported = "CANCEL_REQUESTED"
            except Exception:
                jobs.transition(self._conn, job_id, JobState.CANCELLED)
                reported = "CANCELLED"
            cancel = self._cancels.get(job_id)
            if cancel is not None:
                cancel.set()
            self._bus.publish(
                StreamEvent(
                    kind="state", job_id=job_id, payload={"job_id": job_id, "state": reported}
                )
            )
            return
        raise ValueError(f"job {job_id} is not cancellable from {job.state.value}")

    async def _loop(self) -> None:
        while self._running:
            self._wake.clear()
            self._dispatch_ready()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=0.05)

    def _dispatch_ready(self) -> None:
        if shutil.disk_usage(self._working_dir).free < _MIN_DISK_FREE_BYTES:
            return  # no endless retry: the job stays queued and we emit once
        active = len(self._active)
        if active >= self._limits.max_active:
            return
        queued = jobs.list_jobs(self._conn, states={JobState.QUEUED}, limit=50)
        queued.sort(key=lambda j: (-j.priority, j.created_at, j.id))
        for job in queued:
            if len(self._active) >= self._limits.max_active:
                break
            if job.id in self._active:
                continue
            self._start_job(job.id)

    def _start_job(self, job_id: str) -> None:
        cancel = asyncio.Event()
        self._cancels[job_id] = cancel
        task = asyncio.create_task(self._run_job(job_id, cancel), name=f"job-{job_id}")
        self._active[job_id] = task
        task.add_done_callback(lambda _t, jid=job_id: self._active.pop(jid, None))

    async def _run_job(self, job_id: str, cancel: asyncio.Event) -> None:
        job = jobs.get_job(self._conn, job_id)
        if job is None:
            return
        try:
            jobs.transition(self._conn, job_id, JobState.DOWNLOADING, current_stage="queued")
        except Exception:
            return
        try:
            plan = _parse_plan(job)
            self._bus.publish(
                StreamEvent(
                    kind="scheduler",
                    job_id=job_id,
                    payload={"event": "job_started", "job_id": job_id},
                )
            )
            await self._executor.run(job, plan, cancel)
        except JobCancelled:
            try:
                jobs.transition(self._conn, job_id, JobState.CANCELLED)
            except Exception:
                try:
                    jobs.transition(self._conn, job_id, JobState.CANCEL_REQUESTED)
                    jobs.transition(self._conn, job_id, JobState.CANCELLED)
                except Exception:
                    pass
            self._bus.publish(
                StreamEvent(
                    kind="state", job_id=job_id, payload={"job_id": job_id, "state": "CANCELLED"}
                )
            )
            return
        except ExtractionError as error:
            await self._handle_failure(job_id, error)
            return
        except Exception as error:  # defensive: any tool wrapper escapes as generic
            await self._handle_failure(
                job_id,
                ExtractionError(
                    ErrorCode.EXTRACTION_FAILED, "Job failed.", detail=str(error), retryable=False
                ),
            )
            return
        finally:
            self._cancels.pop(job_id, None)

        # Success path: executor moved the job through PROCESSING/VALIDATING/
        # COMMITTING; it just needs the terminal transition.
        job = jobs.get_job(self._conn, job_id)
        if job is not None and job.state is JobState.COMMITTING:
            jobs.transition(
                self._conn, job_id, JobState.COMPLETED, current_stage="completed", progress=1.0
            )
            self._bus.publish(
                StreamEvent(
                    kind="state",
                    job_id=job_id,
                    payload={"job_id": job_id, "state": "COMPLETED", "percentage": 100.0},
                )
            )
        self._bus.publish(
            StreamEvent(
                kind="scheduler", job_id=job_id, payload={"event": "job_finished", "job_id": job_id}
            )
        )

    async def _handle_failure(self, job_id: str, error: ExtractionError) -> None:
        attempts = jobs.increment_attempts(self._conn, job_id)
        job = jobs.get_job(self._conn, job_id)
        if job is None:
            return
        _log_error_detail(self._working_dir, job_id, error)
        retryable = error.retryable and attempts < self._limits.max_attempts
        if not retryable:
            with suppress(Exception):
                jobs.transition(
                    self._conn,
                    job_id,
                    JobState.FAILED,
                    error_code=error.code.value,
                    error_message=error.message,
                )
            self._bus.publish(
                StreamEvent(
                    kind="state",
                    job_id=job_id,
                    payload={"job_id": job_id, "state": "FAILED", "error_code": error.code.value},
                )
            )
            return
        # bounded retry with backoff through the durable RETRY_WAIT state
        try:
            jobs.transition(self._conn, job_id, JobState.RETRY_WAIT, error_code=error.code.value)
        except Exception:
            return
        self._bus.publish(
            StreamEvent(
                kind="state",
                job_id=job_id,
                payload={"job_id": job_id, "state": "RETRY_WAIT", "error_code": error.code.value},
            )
        )
        await asyncio.sleep(self._limits.retry_backoff_seconds)
        try:
            jobs.transition(self._conn, job_id, JobState.QUEUED)
        except Exception:
            return
        self.wake()


def _log_error_detail(working_dir: str, job_id: str, error: ExtractionError) -> None:
    """Persist raw tool stderr where diagnostics can reach it (SPEC §E)."""
    if not error.detail:
        return
    try:
        from pathlib import Path

        logs = Path(working_dir) / "jobs" / job_id / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "error.log").open("a", encoding="utf-8") as handle:
            handle.write(f"[{error.code.value}] {error.message}\n{error.detail}\n\n")
    except OSError:
        pass


def _parse_plan(job: jobs.Job) -> ExecutionPlan:
    if job.execution_plan_json:
        payload = json.loads(job.execution_plan_json)
        steps = tuple(_step_from_dict(s) for s in payload.get("steps", []) if isinstance(s, dict))
        return ExecutionPlan(steps=steps, strategy=str(payload.get("strategy", "copy")))
    raise ExtractionError(
        ErrorCode.UNSUPPORTED_INTENT,
        "Job has no execution plan.",
        retryable=False,
    )


def _step_from_dict(payload: dict[str, object]) -> PlanStep:
    raw_detail = payload.get("detail")
    detail = {str(k): str(v) for k, v in raw_detail.items()} if isinstance(raw_detail, dict) else {}
    return PlanStep(
        kind=str(payload.get("kind", "")),
        tool=str(payload.get("tool", "")),
        detail=detail,
    )

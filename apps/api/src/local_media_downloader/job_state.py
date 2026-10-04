"""Job lifecycle state machine.

The state row in ``jobs`` is the source of truth. This module is the single
place that decides whether a transition is legal, so the API, the scheduler
and the recovery subsystem can never disagree about it.

Durable-state rule (ENGINEERING_PRINCIPLES #10): in-memory state may be a
cache, never the authoritative job state. Every transition must be written to
SQLite inside one transaction together with its audit event.
"""

from __future__ import annotations

from enum import StrEnum


class JobState(StrEnum):
    CREATED = "CREATED"
    RESOLVING = "RESOLVING"
    READY = "READY"
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING = "PROCESSING"
    VALIDATING = "VALIDATING"
    COMMITTING = "COMMITTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    RETRY_WAIT = "RETRY_WAIT"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


# States that own a live worker process. Startup recovery must reconcile these
# against reality: they may be found after a crash and must never be assumed to
# still have an active process (ARCHITECTURE.md §5, TECHNICAL_SPEC §12).
ACTIVE_STATES: frozenset[JobState] = frozenset(
    {
        JobState.RESOLVING,
        JobState.DOWNLOADING,
        JobState.PROCESSING,
        JobState.VALIDATING,
        JobState.COMMITTING,
    }
)

TERMINAL_STATES: frozenset[JobState] = frozenset(
    {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}
)

# Legal transitions. Anything absent is rejected explicitly (fail explicitly,
# not UNKNOWN_ERROR — ENGINEERING_PRINCIPLES #16).
_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.CREATED: frozenset({JobState.RESOLVING, JobState.FAILED, JobState.CANCELLED}),
    JobState.RESOLVING: frozenset({JobState.READY, JobState.FAILED, JobState.CANCELLED}),
    JobState.READY: frozenset(
        {JobState.QUEUED, JobState.FAILED, JobState.CANCEL_REQUESTED, JobState.CANCELLED}
    ),
    JobState.QUEUED: frozenset(
        {
            JobState.DOWNLOADING,
            JobState.CANCEL_REQUESTED,
            JobState.CANCELLED,
            JobState.FAILED,
            JobState.RECOVERY_REQUIRED,
        }
    ),
    JobState.DOWNLOADING: frozenset(
        {
            JobState.PROCESSING,
            JobState.VALIDATING,
            JobState.RETRY_WAIT,
            JobState.CANCEL_REQUESTED,
            JobState.CANCELLED,
            JobState.FAILED,
            JobState.RECOVERY_REQUIRED,
        }
    ),
    JobState.PROCESSING: frozenset(
        {
            JobState.VALIDATING,
            JobState.RETRY_WAIT,
            JobState.CANCELLED,
            JobState.FAILED,
            JobState.RECOVERY_REQUIRED,
        }
    ),
    JobState.VALIDATING: frozenset(
        {
            JobState.COMMITTING,
            JobState.RETRY_WAIT,
            JobState.FAILED,
            JobState.RECOVERY_REQUIRED,
        }
    ),
    JobState.COMMITTING: frozenset(
        {JobState.COMPLETED, JobState.RETRY_WAIT, JobState.FAILED, JobState.RECOVERY_REQUIRED}
    ),
    # Cancellation is cooperative: the worker observes CANCEL_REQUESTED and
    # stops, so the job waits for a real process to acknowledge it.
    JobState.CANCEL_REQUESTED: frozenset(
        {JobState.CANCELLED, JobState.FAILED, JobState.RECOVERY_REQUIRED}
    ),
    JobState.RETRY_WAIT: frozenset(
        {JobState.QUEUED, JobState.FAILED, JobState.CANCEL_REQUESTED, JobState.CANCELLED}
    ),
    JobState.RECOVERY_REQUIRED: frozenset(
        {JobState.QUEUED, JobState.RETRY_WAIT, JobState.FAILED, JobState.CANCELLED}
    ),
    JobState.COMPLETED: frozenset(),
    JobState.FAILED: frozenset({JobState.RETRY_WAIT}),
    JobState.CANCELLED: frozenset(),
}


class InvalidTransition(ValueError):
    """Raised when a transition is not part of the lifecycle."""

    def __init__(self, current: JobState, target: JobState) -> None:
        super().__init__(f"illegal job transition {current.value} -> {target.value}")
        self.current = current
        self.target = target


def can_transition(current: JobState, target: JobState) -> bool:
    return target in _TRANSITIONS[current]


def assert_transition(current: JobState, target: JobState) -> None:
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


def is_terminal(state: JobState) -> bool:
    return state in TERMINAL_STATES

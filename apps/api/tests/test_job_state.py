from __future__ import annotations

from itertools import pairwise

import pytest

from local_media_downloader.job_state import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    InvalidTransition,
    JobState,
    assert_transition,
    can_transition,
    is_terminal,
)

# The happy path from the lifecycle diagram in ARCHITECTURE.md §5.
HAPPY_PATH = [
    JobState.CREATED,
    JobState.RESOLVING,
    JobState.READY,
    JobState.QUEUED,
    JobState.DOWNLOADING,
    JobState.PROCESSING,
    JobState.VALIDATING,
    JobState.COMMITTING,
    JobState.COMPLETED,
]


def test_every_required_state_exists() -> None:
    assert {s.value for s in JobState} == {
        "CREATED",
        "RESOLVING",
        "READY",
        "QUEUED",
        "DOWNLOADING",
        "PROCESSING",
        "VALIDATING",
        "COMMITTING",
        "COMPLETED",
        "FAILED",
        "CANCEL_REQUESTED",
        "CANCELLED",
        "RETRY_WAIT",
        "RECOVERY_REQUIRED",
    }


def test_happy_path_is_allowed() -> None:
    for current, target in pairwise(HAPPY_PATH):
        assert can_transition(current, target), f"{current} -> {target} should be allowed"


def test_terminal_states_only_allow_an_explicit_retry() -> None:
    """A terminal job is done for that attempt.

    COMPLETED is final; FAILED and CANCELLED may only be re-entered explicitly
    through RETRY_WAIT (the retry endpoint), never silently resumed.
    """
    for state in TERMINAL_STATES:
        for target in JobState:
            allowed = can_transition(state, target)
            if state in {JobState.FAILED, JobState.CANCELLED} and target is JobState.RETRY_WAIT:
                assert allowed, f"{state} must be retryable on purpose"
                continue
            assert not allowed, f"{state} -> {target} must be rejected"


def test_completed_is_terminal_and_failed_can_retry() -> None:
    assert is_terminal(JobState.COMPLETED)
    assert is_terminal(JobState.FAILED)
    assert not is_terminal(JobState.RETRY_WAIT)
    assert can_transition(JobState.FAILED, JobState.RETRY_WAIT)


def test_cannot_skip_resolution() -> None:
    assert not can_transition(JobState.CREATED, JobState.DOWNLOADING)


def test_active_states_cover_execution_ownership() -> None:
    assert JobState.DOWNLOADING in ACTIVE_STATES
    assert JobState.PROCESSING in ACTIVE_STATES
    assert JobState.COMMITTING in ACTIVE_STATES
    assert JobState.COMPLETED not in ACTIVE_STATES


def test_cancellation_is_cooperative() -> None:
    # READY -> CANCEL_REQUESTED -> CANCELLED, never straight to CANCELLED from
    # a state that already owns a live worker.
    assert can_transition(JobState.READY, JobState.CANCEL_REQUESTED)
    assert can_transition(JobState.CANCEL_REQUESTED, JobState.CANCELLED)
    assert not can_transition(JobState.CANCEL_REQUESTED, JobState.DOWNLOADING)


def test_active_states_can_require_recovery() -> None:
    for state in (JobState.DOWNLOADING, JobState.PROCESSING, JobState.VALIDATING):
        assert can_transition(state, JobState.RECOVERY_REQUIRED), state


def test_assert_transition_raises_explicitly() -> None:
    with pytest.raises(InvalidTransition) as exc:
        assert_transition(JobState.CREATED, JobState.COMPLETED)
    assert exc.value.current is JobState.CREATED
    assert exc.value.target is JobState.COMPLETED
    assert "CREATED -> COMPLETED" in str(exc.value)

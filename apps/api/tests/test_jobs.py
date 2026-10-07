from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from local_media_downloader.db import initialize
from local_media_downloader.job_state import InvalidTransition, JobState
from local_media_downloader.jobs import (
    MAX_PAGE_SIZE,
    create_job,
    cursor_of,
    find_active_jobs,
    get_events,
    get_job,
    hash_url,
    list_jobs,
    transition,
)

URL = "https://example.com/watch?v=abc123"


@pytest.fixture
def conn(tmp_path):
    connection = initialize(tmp_path / "app.db")
    try:
        yield connection
    finally:
        connection.close()


def test_create_job_starts_in_created_with_audit_event(conn) -> None:
    job = create_job(conn, source_url=URL, created_by="extension")
    assert job.state is JobState.CREATED
    assert job.source_url == URL
    assert job.source_url_hash == hash_url(URL)
    assert job.created_by == "extension"
    assert job.priority == 0

    events = get_events(conn, job.id)
    assert [e["event_type"] for e in events] == ["JOB_CREATED"]


def test_get_job_returns_none_for_unknown(conn) -> None:
    assert get_job(conn, "does-not-exist") is None


def test_transition_writes_state_and_event_atomically(conn) -> None:
    job = create_job(conn, source_url=URL)
    updated = transition(conn, job.id, JobState.RESOLVING)

    assert updated.state is JobState.RESOLVING
    assert updated.updated_at >= job.updated_at

    events = get_events(conn, job.id)
    assert [e["event_type"] for e in events] == ["JOB_CREATED", "STATE_CHANGED"]
    payload = json.loads(events[-1]["payload_json"])
    assert payload == {"from": "CREATED", "to": "RESOLVING"}


def test_illegal_transition_is_rejected_and_state_is_unchanged(conn) -> None:
    job = create_job(conn, source_url=URL)
    with pytest.raises(InvalidTransition):
        transition(conn, job.id, JobState.COMPLETED)
    unchanged = get_job(conn, job.id)
    assert unchanged is not None
    assert unchanged.state is JobState.CREATED


def test_error_metadata_is_recorded_on_failure(conn) -> None:
    job = create_job(conn, source_url=URL)
    failed = transition(
        conn,
        job.id,
        JobState.FAILED,
        error_code="UNSUPPORTED_SOURCE",
        error_message="extractor not available",
    )
    assert failed.error_code == "UNSUPPORTED_SOURCE"
    assert failed.error_message == "extractor not available"

    payload = json.loads(get_events(conn, job.id)[-1]["payload_json"])
    assert payload["error_code"] == "UNSUPPORTED_SOURCE"


def test_full_lifecycle_to_completed(conn) -> None:
    job = create_job(conn, source_url=URL)
    for target in (
        JobState.RESOLVING,
        JobState.READY,
        JobState.QUEUED,
        JobState.DOWNLOADING,
        JobState.PROCESSING,
        JobState.VALIDATING,
        JobState.COMMITTING,
        JobState.COMPLETED,
    ):
        job = transition(
            conn, job.id, target, progress=1.0 if target is JobState.COMPLETED else None
        )
    assert job.state is JobState.COMPLETED
    assert job.progress == 1.0
    assert len(get_events(conn, job.id)) == 9  # 1 created + 8 transitions


def test_event_payload_never_contains_the_source_url(conn) -> None:
    job = create_job(conn, source_url=URL)
    transition(conn, job.id, JobState.RESOLVING)
    transition(conn, job.id, JobState.FAILED, error_code="NETWORK_LOSS")
    payloads = " ".join((e["payload_json"] or "") for e in get_events(conn, job.id))
    assert URL not in payloads
    assert "example.com" not in payloads


def test_list_jobs_filters_by_state_and_orders_by_priority(conn) -> None:
    low = create_job(conn, source_url="https://a.example/1", priority=0)
    high = create_job(conn, source_url="https://a.example/2", priority=5)
    transition(conn, high.id, JobState.RESOLVING)

    queued = list_jobs(conn, states={JobState.RESOLVING})
    assert [j.id for j in queued] == [high.id]

    everything = list_jobs(conn)
    assert [j.id for j in everything] == [high.id, low.id]


def test_list_jobs_requires_a_positive_limit(conn) -> None:
    with pytest.raises(ValueError):
        list_jobs(conn, limit=0)


def test_list_jobs_caps_the_page_size(conn) -> None:

    assert list_jobs(conn, limit=MAX_PAGE_SIZE * 10) == list_jobs(conn, limit=MAX_PAGE_SIZE)


def test_cursor_pagination_visits_every_job_exactly_once(conn) -> None:
    """Keyset pagination must not skip or duplicate rows.

    This is why `id` is the final ORDER BY term: created_at has millisecond
    resolution, so a page boundary can easily land on two rows that compare
    equal on (priority, created_at).
    """
    created = [create_job(conn, source_url=f"https://a.example/{i}") for i in range(25)]

    seen: list[str] = []
    cursor = None
    while True:
        page = list_jobs(conn, limit=7, cursor=cursor)
        if not page:
            break
        seen.extend(j.id for j in page)
        cursor = cursor_of(page[-1])

    assert len(seen) == len(set(seen)), "a job was returned twice"
    assert set(seen) == {j.id for j in created}


def test_cursor_pagination_holds_when_sort_keys_collide(conn) -> None:
    """Force identical (priority, created_at) so only `id` can break the tie."""
    ids = []
    for i in range(10):
        job = create_job(conn, source_url=f"https://a.example/{i}", priority=0)
        ids.append(job.id)
    # Collapse every timestamp and priority onto one value.
    conn.execute("UPDATE jobs SET created_at = '2026-01-01T00:00:00.000+00:00', priority = 0")

    seen: list[str] = []
    cursor = None
    while True:
        page = list_jobs(conn, limit=3, cursor=cursor)
        if not page:
            break
        seen.extend(j.id for j in page)
        cursor = cursor_of(page[-1])

    assert len(seen) == len(set(seen))
    assert set(seen) == set(ids)


def test_cursor_is_respected_when_filtering_by_state(conn) -> None:
    ready = create_job(conn, source_url="https://a.example/r")
    transition(conn, ready.id, JobState.RESOLVING)
    transition(conn, ready.id, JobState.READY)
    create_job(conn, source_url="https://a.example/q")

    page = list_jobs(conn, states={JobState.READY}, limit=1)
    assert [j.id for j in page] == [ready.id]
    # A different filter must not leak rows through the cursor.
    rest = list_jobs(conn, states={JobState.CREATED}, limit=1, cursor=cursor_of(page[0]))
    assert [j.id for j in rest] != [ready.id]


def test_transition_unknown_job_raises(conn) -> None:
    with pytest.raises(KeyError):
        transition(conn, "ghost", JobState.RESOLVING)


def test_active_jobs_are_found_after_process_termination(tmp_path) -> None:
    """Acceptance: a job can be recovered after process termination.

    Simulates a crash by dropping the connection mid-flight (no clean close)
    and reopening the database from disk, exactly as a restart would.
    """
    database = tmp_path / "app.db"

    conn = initialize(database)
    job = create_job(conn, source_url=URL)
    transition(conn, job.id, JobState.RESOLVING)
    transition(conn, job.id, JobState.READY)
    transition(conn, job.id, JobState.QUEUED)
    transition(conn, job.id, JobState.DOWNLOADING)
    conn.close()  # process "dies" here, with DOWNLOADING persisted

    # --- restart ---
    reopened = initialize(database)
    try:
        orphans = find_active_jobs(reopened)
        assert [j.id for j in orphans] == [job.id]
        assert orphans[0].state is JobState.DOWNLOADING

        # The reconciler decides it is not safely resumable yet.
        recovered = transition(reopened, job.id, JobState.RECOVERY_REQUIRED)
        assert recovered.state is JobState.RECOVERY_REQUIRED

        # And it can be re-queued for another attempt.
        requeued = transition(reopened, job.id, JobState.QUEUED)
        assert requeued.state is JobState.QUEUED
        # 1 JOB_CREATED + 4 pre-crash transitions + 2 post-restart transitions.
        events = get_events(reopened, job.id)
        assert len(events) == 7
        assert [e["event_type"] for e in events[:5]] == ["JOB_CREATED"] + ["STATE_CHANGED"] * 4
    finally:
        reopened.close()


def test_history_survives_reopen(tmp_path) -> None:
    database = tmp_path / "app.db"
    conn = initialize(database)
    job = create_job(conn, source_url=URL)
    conn.close()

    reopened = initialize(database)
    try:
        stored = get_job(reopened, job.id)
        assert stored is not None
        assert stored.source_url == URL
        assert stored.state is JobState.CREATED
        assert get_events(reopened, job.id)[0]["event_type"] == "JOB_CREATED"
    finally:
        reopened.close()


def test_deleting_a_job_cascades_events(conn) -> None:
    job = create_job(conn, source_url=URL)
    conn.execute("DELETE FROM jobs WHERE id = ?", (job.id,))
    assert get_events(conn, job.id) == []
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO job_events (job_id, timestamp, event_type) VALUES (?, 'now', 'X')",
            (job.id,),
        )


_DEDUPE_INTENT = {
    "media": "video",
    "quality": "best",
    "container": "mp4",
    "audio": "include",
    "video_codec": "source",
}


def test_find_duplicate_returns_non_terminal_job_with_same_key(conn) -> None:
    from local_media_downloader.domain.dedupe import dedupe_key
    from local_media_downloader.jobs import find_duplicate

    intent = dict(_DEDUPE_INTENT)
    key = dedupe_key(URL, intent)
    job = create_job(conn, source_url=URL, dedupe_key=key, state=JobState.QUEUED)
    found = find_duplicate(conn, key)
    assert found is not None
    assert found.id == job.id


def test_find_duplicate_ignores_terminal_jobs(conn) -> None:
    from local_media_downloader.domain.dedupe import dedupe_key
    from local_media_downloader.jobs import find_duplicate

    intent = dict(_DEDUPE_INTENT)
    key = dedupe_key(URL, intent)
    job = create_job(conn, source_url=URL, dedupe_key=key, state=JobState.QUEUED)
    transition(conn, job.id, JobState.DOWNLOADING)
    transition(conn, job.id, JobState.FAILED)
    assert find_duplicate(conn, key) is None


def test_clear_source_url_keeps_hash(conn) -> None:
    from local_media_downloader.jobs import clear_source_url

    job = create_job(conn, source_url=URL)
    clear_source_url(conn, job.id)
    updated = get_job(conn, job.id)
    assert updated is not None
    assert updated.source_url is None
    assert updated.source_url_hash == hash_url(URL)


def test_delete_job_removes_row(conn) -> None:
    from local_media_downloader.jobs import delete_job

    job = create_job(conn, source_url=URL)
    assert delete_job(conn, job.id) is True
    assert get_job(conn, job.id) is None
    assert delete_job(conn, job.id) is False


def test_list_terminal_older_than_filters_by_age(conn) -> None:
    from local_media_downloader.jobs import list_terminal_older_than

    job = create_job(conn, source_url=URL, state=JobState.QUEUED)
    transition(conn, job.id, JobState.DOWNLOADING)
    transition(conn, job.id, JobState.FAILED)
    old = (datetime.now(UTC) - timedelta(days=5)).isoformat(timespec="milliseconds")
    conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (old, job.id))
    conn.commit()
    found = list_terminal_older_than(conn, (datetime.now(UTC) - timedelta(days=1)).isoformat())
    assert len(found) == 1
    assert found[0].id == job.id


def test_set_priority_updates_queue_order(conn) -> None:
    from local_media_downloader.jobs import set_priority

    job = create_job(conn, source_url=URL)
    updated = set_priority(conn, job.id, 10)
    assert updated.priority == 10


def test_reset_for_retry_clears_attempts_and_errors(conn) -> None:
    from local_media_downloader.jobs import reset_for_retry

    job = create_job(conn, source_url=URL, state=JobState.QUEUED)
    transition(conn, job.id, JobState.DOWNLOADING)
    transition(conn, job.id, JobState.FAILED, error_code="NETWORK_ERROR")
    reset_for_retry(conn, job.id)
    updated = get_job(conn, job.id)
    assert updated is not None
    assert updated.attempt_count == 0
    assert updated.error_code is None
    assert updated.error_message is None

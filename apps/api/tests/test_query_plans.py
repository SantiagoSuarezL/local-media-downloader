"""Query-plan regression guard.

Measured facts this test protects (SQLite 3.x, this schema):

- `get_job` and `get_events` must use an index, not scan.
- `list_jobs` and its keyset cursor must ride `idx_jobs_sort` with no temp
  b-tree. Measured on 50k jobs: shallow page 26.10 ms -> 0.18 ms, deep page
  12.92 ms -> 5.86 ms, at a cost of 3.7 -> 4.0 us/row on state transitions.
- Two indexes were tried and REJECTED because they did not remove the temp
  b-tree (a multi-state IN clause cannot be served by (state, priority,
  created_at)) while costing ~3x on writes: 10.2 us/row with them versus
  3.5 us/row without. Do not add them back.

If this test fails, an index was dropped in a migration, not that the code got
slower.
"""

from __future__ import annotations

import sqlite3

import pytest

from local_media_downloader.db import initialize
from local_media_downloader.jobs import create_job, get_events, get_job


@pytest.fixture
def conn(tmp_path):
    connection = initialize(tmp_path / "app.db")
    try:
        yield connection
    finally:
        connection.close()


def _plan(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> str:
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return " | ".join(r["detail"] for r in rows)


def test_lookup_by_id_is_indexed(conn) -> None:
    job = create_job(conn, source_url="https://example.com/a")
    plan = _plan(conn, "SELECT * FROM jobs WHERE id = ?", (job.id,))
    assert "SEARCH" in plan, plan
    assert "SCAN jobs" not in plan, plan
    assert get_job(conn, job.id) is not None


def test_events_by_job_are_indexed(conn) -> None:
    job = create_job(conn, source_url="https://example.com/b")
    plan = _plan(conn, "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job.id,))
    assert "SEARCH" in plan, plan
    assert "idx_job_events_job_id" in plan, plan
    assert get_events(conn, job.id)


def test_filter_by_state_is_indexed(conn) -> None:
    create_job(conn, source_url="https://example.com/c")
    plan = _plan(
        conn,
        "SELECT * FROM jobs WHERE state IN (?)"
        " ORDER BY priority DESC, created_at DESC, id DESC LIMIT ?",
        ("CREATED", 10),
    )
    assert "SEARCH" in plan, plan
    assert "idx_jobs_state" in plan, plan


def test_foreign_key_cascade_delete_is_indexed(conn) -> None:
    """Deleting a job must not scan every event row."""
    job = create_job(conn, source_url="https://example.com/d")
    plan = _plan(conn, "DELETE FROM jobs WHERE id = ?", (job.id,))
    assert "SEARCH" in plan, plan


def test_history_list_may_scan_and_that_is_accepted(conn) -> None:
    """The unfiltered history list reads the sort index in order, no temp sort."""
    create_job(conn, source_url="https://example.com/e")
    plan = _plan(
        conn,
        "SELECT * FROM jobs ORDER BY priority DESC, created_at DESC, id DESC LIMIT ?",
        (100,),
    )
    assert "TEMP B-TREE" not in plan.upper(), plan

    from local_media_downloader.jobs import MAX_PAGE_SIZE, list_jobs

    assert MAX_PAGE_SIZE == 500
    assert len(list_jobs(conn, limit=10_000)) <= MAX_PAGE_SIZE


def test_cursor_pagination_has_no_temp_sort(conn) -> None:
    """The keyset cursor must ride the sort index, not scan-and-sort.

    This is the index that the earlier "add an index everywhere" advice would
    have produced for the wrong reason; it is here because the measurement in
    migration v2 shows a 145x page-latency win for an 8% write cost.
    """
    plan = _plan(
        conn,
        "SELECT * FROM jobs WHERE (priority < ? OR (priority = ? AND"
        " (created_at < ? OR (created_at = ? AND id < ?))))"
        " ORDER BY priority DESC, created_at DESC, id DESC LIMIT ?",
        (0, 0, "x", "x", "y", 50),
    )
    assert "TEMP B-TREE" not in plan.upper(), plan
    assert "idx_jobs_sort" in plan, plan


def test_every_query_issued_by_the_repository_is_bounded(conn) -> None:
    """A cursor page stops at the previous row instead of skipping ahead."""
    from local_media_downloader.jobs import cursor_of, list_jobs

    create_job(conn, source_url="https://example.com/f")
    first = list_jobs(conn, limit=1)
    assert len(first) == 1
    # Only one job exists, so the page after the cursor must be empty rather
    # than wrapping around to the row we already saw.
    assert list_jobs(conn, limit=1, cursor=cursor_of(first[0])) == []

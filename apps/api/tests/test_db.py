from __future__ import annotations

import sqlite3

import pytest

from local_media_downloader.db import connect, initialize, schema_version, transaction
from local_media_downloader.migrations import MIGRATIONS, current_version, migrate


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "app.db"


def test_migrations_apply_and_are_idempotent(db_path) -> None:
    conn = initialize(db_path)
    try:
        assert schema_version(conn) == MIGRATIONS[-1][0]
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"jobs", "job_events", "settings"} <= tables
        # Re-running must be a no-op, not an error.
        assert migrate(conn) == MIGRATIONS[-1][0]
    finally:
        conn.close()


def test_wal_and_pragmas_are_enabled(db_path) -> None:
    conn = initialize(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_foreign_keys_are_enforced(db_path) -> None:
    conn = initialize(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO job_events (job_id, timestamp, event_type)"
                " VALUES ('ghost', 'now', 'X')"
            )
    finally:
        conn.close()


def test_migration_versions_are_unique_and_ordered() -> None:
    versions = [version for version, _desc, _sql in MIGRATIONS]
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)
    assert versions[0] == 1


def test_v2_database_upgrades_to_v3_with_old_rows_intact(tmp_path) -> None:
    """Phase 12: pre-migration rows survive and read back with a NULL key."""
    from local_media_downloader.jobs import find_duplicate, get_job

    raw = sqlite3.connect(tmp_path / "old.db")
    try:
        for target, _desc, sql in MIGRATIONS:
            if target > 2:
                break
            raw.executescript(sql)
            raw.execute(f"PRAGMA user_version = {target}")
            raw.commit()
        raw.execute(
            "INSERT INTO jobs (id, created_at, updated_at, state, source_url,"
            " source_url_hash, title, created_by, priority)"
            " VALUES ('old-1', 't', 't', 'COMPLETED', 'https://example.com/v', 'h',"
            " 'Old', 'ui', 0)"
        )
        raw.commit()
    finally:
        raw.close()

    conn = initialize(tmp_path / "old.db")
    try:
        assert schema_version(conn) == 3
        old = get_job(conn, "old-1")
        assert old is not None
        assert old.dedupe_key is None
        # Old rows carry no key, so they never match a duplicate lookup.
        assert find_duplicate(conn, "whatever") is None
    finally:
        conn.close()


def test_fresh_database_starts_at_version_zero(tmp_path) -> None:
    conn = sqlite3.connect(tmp_path / "raw.db")
    try:
        assert current_version(conn) == 0
    finally:
        conn.close()


def test_transaction_rolls_back_on_error(db_path) -> None:
    conn = initialize(db_path)
    try:
        conn.execute("INSERT INTO settings (key, value_json, updated_at) VALUES ('k', '1', 'now')")
        with pytest.raises(RuntimeError), transaction(conn):
            conn.execute(
                "INSERT INTO settings (key, value_json, updated_at) VALUES ('k2', '2', 'now')"
            )
            raise RuntimeError("boom")
        rows = conn.execute("SELECT key FROM settings").fetchall()
        assert [r["key"] for r in rows] == ["k"]
    finally:
        conn.close()


def test_connect_creates_parent_directory(tmp_path) -> None:
    nested = tmp_path / "a" / "b" / "app.db"
    conn = connect(nested)
    try:
        assert nested.exists()
    finally:
        conn.close()

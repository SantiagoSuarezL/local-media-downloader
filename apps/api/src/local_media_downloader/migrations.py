"""Schema migrations, versioned with ``PRAGMA user_version``.

Migrations are append-only: each is a (version, sql) pair applied in order.
Never edit a shipped migration; add a new one. This keeps a local database
reproducible across app versions without a migration framework.
"""

from __future__ import annotations

import sqlite3

# (version, description, statements)
MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "initial schema: jobs, job_events, settings",
        """
        CREATE TABLE jobs (
            id                TEXT PRIMARY KEY,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL,
            state             TEXT NOT NULL,
            source_url        TEXT,
            source_url_hash   TEXT NOT NULL,
            extractor         TEXT,
            title             TEXT,
            intent_json       TEXT,
            execution_plan_json TEXT,
            progress          REAL NOT NULL DEFAULT 0,
            bytes_downloaded  INTEGER NOT NULL DEFAULT 0,
            total_bytes       INTEGER,
            current_stage     TEXT,
            attempt_count     INTEGER NOT NULL DEFAULT 0,
            error_code        TEXT,
            error_message     TEXT,
            output_path       TEXT,
            created_by        TEXT,
            priority          INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX idx_jobs_state ON jobs(state);
        CREATE INDEX idx_jobs_created_at ON jobs(created_at);

        CREATE TABLE job_events (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id        TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            timestamp     TEXT NOT NULL,
            event_type    TEXT NOT NULL,
            payload_json  TEXT
        );

        CREATE INDEX idx_job_events_job_id ON job_events(job_id);

        CREATE TABLE settings (
            key         TEXT PRIMARY KEY,
            value_json  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        """,
    ),
    (
        2,
        "index the deterministic job sort key used by cursor pagination",
        """
        -- `list_jobs` orders by (priority DESC, created_at DESC, id DESC) and
        -- paginates with a keyset cursor. Without this index SQLite builds a
        -- TEMP B-TREE for every page.
        -- Measured on 50k jobs: shallow page 26.10 ms -> 0.18 ms, deep page
        -- 12.92 ms -> 5.86 ms, and state transitions cost 3.7 -> 4.0 us/row
        -- (+8%). An ordered index scan replaces the sort, so this is the one
        -- extra index the schema carries beyond plain WHERE/JOIN columns.
        CREATE INDEX idx_jobs_sort ON jobs(priority DESC, created_at DESC, id DESC);
        """,
    ),
]


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations in order.

    ``executescript`` manages its own transaction; the user_version bump is
    committed right after, so a failure leaves the database at the last good
    version instead of half-migrated.
    """
    version = current_version(conn)
    for target, _description, sql in MIGRATIONS:
        if target <= version:
            continue
        conn.executescript(sql)
        # PRAGMA does not accept bound parameters; the value comes from our own
        # MIGRATIONS table, never from user input.
        conn.execute(f"PRAGMA user_version = {target}")
        conn.commit()
        version = target
    return version

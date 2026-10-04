"""SQLite connection management.

Direct sqlite3 from the standard library — no ORM (TECHNICAL_SPEC §25: avoid an
ORM when direct SQLite is sufficient). Connections are per-thread; the service
is a single-process local app, so there is no pool to maintain yet.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .migrations import current_version, migrate


def connect(database_path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    if database_path.parent and not database_path.parent.exists():
        database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        database_path,
        # We manage transactions explicitly so state transitions are atomic.
        isolation_level=None,
        check_same_thread=False,
        uri=read_only,
    )
    conn.row_factory = sqlite3.Row
    # WAL lets the API read while a worker writes. foreign_keys is off by
    # default in SQLite and must be enabled per connection.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    # NORMAL is the documented WAL-safe setting: durable across app crashes,
    # may lose the last transactions only on OS crash/power loss.
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def initialize(database_path: Path) -> sqlite3.Connection:
    """Open a connection and bring the schema up to date. Idempotent."""
    conn = connect(database_path)
    migrate(conn)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Explicit transaction boundary (BEGIN IMMEDIATE ... COMMIT/ROLLBACK).

    BEGIN IMMEDIATE takes the write lock up front so a state transition never
    fails halfway with a mid-transaction busy error.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def schema_version(conn: sqlite3.Connection) -> int:
    return current_version(conn)

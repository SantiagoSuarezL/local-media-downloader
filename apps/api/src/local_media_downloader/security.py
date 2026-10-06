"""Loopback security policy (Phase 10).

``localhost`` is only a convention: any other process on the machine can reach
the port, and any web page can try to make the browser talk to it. This module
holds the three checks that make loopback a real boundary:

1. **Bind** — the service only ever listens on a loopback address
   (:func:`assert_loopback_host`), so it is unreachable from the network.
2. **Host/Origin** — every request must present a loopback ``Host`` and, when
   present, a loopback ``Origin`` (:func:`validate_host`, :func:`validate_origin`).
   This is what stops DNS rebinding: a page at ``evil.com`` that resolves to
   127.0.0.1 still sends ``Host: evil.com`` and is rejected.
3. **Token** — a per-installation secret (:func:`load_or_create_token`) required
   on every API call, so another local process cannot drive the API even though
   it can open the port. The token lives in the ``settings`` table next to the
   rest of the durable state and is never logged.

Comparisons are constant-time: a token is a secret even on a loopback socket.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import UTC, datetime
from urllib.parse import urlsplit

from .logging_config import register_secret

TOKEN_HEADER = "x-lmd-token"
_TOKEN_KEY = "auth_token"
_TOKEN_BYTES = 32

# The service never needs a hostname other than these; they are the only Host
# values a legitimate browser request carries.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


class SecurityError(Exception):
    """A request refused at the boundary. Never carries request content."""

    def __init__(self, code: str, message: str, *, status_code: int = 403) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def assert_loopback_host(host: str) -> None:
    """Fail fast when the configured bind address is not loopback."""
    if _host_of(host) not in LOOPBACK_HOSTS:
        raise SecurityError(
            "NON_LOOPBACK_BIND",
            f"Refusing to bind {host!r}: the service only listens on loopback "
            f"({', '.join(sorted(LOOPBACK_HOSTS))}).",
            status_code=500,
        )


def load_or_create_token(conn: sqlite3.Connection) -> str:
    """Return the installation token, generating and persisting it if absent.

    Stored in the ``settings`` table so it survives restarts: rotating it on
    every boot would break the already-open dashboard for no security gain.
    """
    row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (_TOKEN_KEY,)).fetchone()
    if row is not None:
        try:
            stored = json.loads(row["value_json"])
        except (TypeError, ValueError):
            stored = None
        if isinstance(stored, str) and stored:
            register_secret(stored)
            return stored

    token = secrets.token_urlsafe(_TOKEN_BYTES)
    now = datetime.now(UTC).isoformat(timespec="milliseconds")
    conn.execute(
        "INSERT INTO settings (key, value_json, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, "
        "updated_at = excluded.updated_at",
        (_TOKEN_KEY, json.dumps(token), now),
    )
    conn.commit()
    register_secret(token)
    return token


def validate_host(host_header: str | None, *, expected_port: int | None = None) -> None:
    """Reject any request whose Host is not this loopback service."""
    if not host_header:
        raise SecurityError("INVALID_HOST", "Missing Host header.", status_code=400)
    # The header carries `host[:port]` with no scheme; _host_of adds one.
    host = _host_of(host_header)
    if host not in LOOPBACK_HOSTS:
        raise SecurityError(
            "INVALID_HOST",
            "Requests must address the local service through a loopback host.",
        )
    port = _port_of(host_header)
    if expected_port is not None and port is not None and port != expected_port:
        raise SecurityError(
            "INVALID_HOST",
            "Requests must address the configured service port.",
        )


def validate_origin(origin: str | None) -> None:
    """Allow a missing Origin (CLI, curl) and loopback origins only.

    A literal ``null`` origin comes from a sandboxed or opaque context and is
    rejected: it identifies no verifiable site, so it can only weaken the check.
    """
    if origin is None:
        return
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or _host_of(origin) not in LOOPBACK_HOSTS:
        raise SecurityError("INVALID_ORIGIN", "Cross-origin requests are not allowed.")


def token_matches(provided: str | None, expected: str) -> bool:
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


def _host_of(url_like: str) -> str:
    """Hostname of ``url_like`` (a URL or a bare ``host[:port]``), lowercased."""
    candidate = url_like if "://" in url_like else f"http://{url_like}"
    try:
        parsed = urlsplit(candidate)
        return (parsed.hostname or "").lower()
    except ValueError:
        return ""


def _port_of(host_header: str) -> int | None:
    try:
        return urlsplit(f"http://{host_header}").port
    except ValueError:
        return None

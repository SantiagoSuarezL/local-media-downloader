"""URL admission policy.

The local API is a security boundary even on loopback
(ENGINEERING_PRINCIPLES #18), so a URL is validated before it can reach a
tool. Only ``http``/``https`` are accepted; ``file:``, ``javascript:``,
``data:`` and arbitrary local-resource schemes are rejected outright
(PRD security requirements).

Phase 10 hardens this further (DNS-rebinding resistance, redirect policy,
protocol allowlist per source); this is the minimum admission gate.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .errors import ErrorCode, ExtractionError

ALLOWED_SCHEMES = frozenset({"http", "https"})


def validate_url(url: str) -> str:
    """Return the URL unchanged, or raise :class:`ExtractionError`."""
    candidate = url.strip()
    if not candidate:
        raise ExtractionError(ErrorCode.INVALID_URL, "The URL is empty.")

    parts = urlsplit(candidate)
    if not parts.scheme:
        raise ExtractionError(
            ErrorCode.INVALID_URL, "The URL has no scheme; expected http or https."
        )
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ExtractionError(
            ErrorCode.UNSUPPORTED_PROTOCOL,
            f"Protocol '{scheme}:' is not supported. Use http or https.",
        )
    if not parts.netloc:
        raise ExtractionError(ErrorCode.INVALID_URL, "The URL has no host.")
    return candidate

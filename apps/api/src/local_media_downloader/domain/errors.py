"""Domain error taxonomy.

Error categories are part of the UX, not an implementation detail
(ENGINEERING_PRINCIPLES #16): an unsupported URL must surface as
``UNSUPPORTED_SOURCE``, never as ``UNKNOWN_ERROR``. Every code carries whether a
retry could plausibly succeed, which the scheduler needs in Phase 6 and recovery
needs in Phase 7.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable, user-facing error categories."""

    # Request / input
    INVALID_URL = "INVALID_URL"
    UNSUPPORTED_PROTOCOL = "UNSUPPORTED_PROTOCOL"
    # A URL that points at this machine or the local network (SSRF guard).
    BLOCKED_SOURCE = "BLOCKED_SOURCE"

    # Source availability
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    GEO_RESTRICTED = "GEO_RESTRICTED"
    AGE_RESTRICTED = "AGE_RESTRICTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    DRM_PROTECTED = "DRM_PROTECTED"
    LIVE_STREAM = "LIVE_STREAM"

    # Environment
    TOOL_MISSING = "TOOL_MISSING"
    TOOL_OUTDATED = "TOOL_OUTDATED"
    INSUFFICIENT_DISK = "INSUFFICIENT_DISK"

    # Transient
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"

    # Fallback — only when the cause genuinely cannot be classified.
    EXTRACTION_FAILED = "EXTRACTION_FAILED"

    # A produced file failed post-processing validation (FFprobe checks).
    VALIDATION_FAILED = "VALIDATION_FAILED"

    # Intent that cannot be mapped to a safe execution plan.
    UNSUPPORTED_INTENT = "UNSUPPORTED_INTENT"


# Retryable means "the same request may succeed later without user action".
RETRYABLE: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.NETWORK_ERROR,
        ErrorCode.TIMEOUT,
        ErrorCode.RATE_LIMITED,
        ErrorCode.SOURCE_UNAVAILABLE,
        ErrorCode.TOOL_OUTDATED,
    }
)


class ExtractionError(Exception):
    """A classified extraction failure.

    ``detail`` keeps the raw tool message for diagnostics only; it must never be
    shown verbatim as the user-facing error, and must never contain secrets.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        detail: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.retryable = code in RETRYABLE if retryable is None else retryable

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"

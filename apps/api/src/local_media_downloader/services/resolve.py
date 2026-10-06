"""Resolve a URL into normalized media information.

Deliberately thin: validate, delegate to the extractor port, normalize. The
Phase 5 planner will consume the ``MediaInfo`` this returns.
"""

from __future__ import annotations

from ..domain.errors import ErrorCode, ExtractionError
from ..domain.extractor import Extractor
from ..domain.media import MediaInfo
from ..domain.urls import validate_url
from ..logging_config import get_logger

_LOGGER = get_logger("service.resolve")

DEFAULT_TIMEOUT = 30.0


class ResolveService:
    def __init__(self, extractor: Extractor, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._extractor = extractor
        self._timeout = timeout

    def resolve(self, url: str) -> MediaInfo:
        # Policy is enforced here, at the service boundary, so no extractor
        # implementation can be handed a URL that was never admitted.
        validated = validate_url(url)
        info = self._extractor.resolve(validated, timeout=self._timeout)
        _LOGGER.info(
            "resolve_ok",
            extra={"extractor": self._extractor.name, "format_count": len(info.formats)},
        )
        return info


# HTTP status per error category. The code, not the status, is the contract the
# UI keys on; the status exists so generic HTTP clients behave sensibly.
_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.INVALID_URL: 400,
    ErrorCode.UNSUPPORTED_PROTOCOL: 400,
    # The user asked for something that cannot be a source at all (SSRF guard).
    ErrorCode.BLOCKED_SOURCE: 400,
    ErrorCode.UNSUPPORTED_SOURCE: 422,
    ErrorCode.SOURCE_UNAVAILABLE: 422,
    ErrorCode.GEO_RESTRICTED: 422,
    ErrorCode.AGE_RESTRICTED: 422,
    ErrorCode.AUTH_REQUIRED: 422,
    ErrorCode.DRM_PROTECTED: 422,
    ErrorCode.LIVE_STREAM: 422,
    # An intent or a produced file that cannot be honoured. These are user
    # mistakes, not server faults: defaulting them to 500 would make the UI
    # report an internal error for a bad dropdown choice.
    ErrorCode.UNSUPPORTED_INTENT: 422,
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.TOOL_MISSING: 503,
    ErrorCode.TOOL_OUTDATED: 503,
    ErrorCode.INSUFFICIENT_DISK: 507,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.NETWORK_ERROR: 502,
    ErrorCode.TIMEOUT: 504,
    ErrorCode.EXTRACTION_FAILED: 502,
}


def error_response(error: ExtractionError) -> tuple[int, dict[str, object]]:
    """Map a domain error onto an HTTP status and the standard error envelope."""
    status = _STATUS_BY_CODE.get(error.code, 500)
    payload: dict[str, object] = {
        "error": {
            "code": error.code.value,
            "message": error.message,
            "retryable": error.retryable,
        }
    }
    return status, payload

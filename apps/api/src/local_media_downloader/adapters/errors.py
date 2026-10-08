"""yt-dlp error classification.

Maps raw yt-dlp stderr onto the domain error taxonomy. The mapping is data, not
control flow, so it can be unit-tested exhaustively without spawning a process
(ENGINEERING_PRINCIPLES #16: an unsupported URL must not surface as
UNKNOWN_ERROR).

Matching is ordered: the first pattern that matches wins, so more specific
causes are listed before generic ones.
"""

from __future__ import annotations

import re

from ..domain.errors import ErrorCode, ExtractionError

# Long patterns kept as named constants so the rule table stays readable and no
# line has to wrap inside a raw string.
_AGE = r"(sign in to confirm your age|age.?restricted|inappropriate for some users)"
_SIGN_IN = r"(sign in to confirm|login required|this video is private|private video|cookies)"
_GEO = r"(available in your country|geo.?restrict|geo.?blocked)"
_LIVE = r"(live event will begin|this live event|is live)"
# 429 is excluded here because it has its own, more specific category.
_UNAVAILABLE = (
    r"(http error 4(?!29)\d\d|video unavailable|has been removed"
    r"|no longer available|unable to extract|dead page)"
)
_NO_FORMAT = r"(requested format is not available|format is not available|no video formats found)"
# DNS failure wording is platform-specific: Winsock says "getaddrinfo failed"
# while glibc says "Name or service not known" (urllib3: "Failed to resolve").
# All of them must land here, before _BROKEN_EXTRACTOR below, or the same
# unresolvable host classifies as NETWORK_ERROR on Windows but TOOL_OUTDATED
# on Linux (the CI ubuntu backend failure).
_NETWORK = (
    r"(read timed out|timed out|timeout|connection reset|connection aborted"
    r"|temporary failure in name resolution|name or service not known"
    r"|failed to resolve|name resolution|nodename nor servname"
    r"|network is unreachable|connection refused|ssl|getaddrinfo)"
)
_RATE_LIMIT = r"(too many requests|rate.?limit|http error 429)"
_NO_DISK = r"(no space left on device|disk full|enospc)"
_NO_BINARY = r"(executable not found|no such file or directory.*yt.?dlp)"
_BROKEN_EXTRACTOR = r"(unable to download (api page|webpage)|json|extractor)"

# (compiled pattern, code, user-facing message, retryable override)
_RULES: list[tuple[re.Pattern[str], ErrorCode, str, bool | None]] = [
    (
        re.compile(r"unsupported url", re.I),
        ErrorCode.UNSUPPORTED_SOURCE,
        "This site is not supported by the local extractor.",
        False,
    ),
    (
        re.compile(r"(drm|protected content|widevine)", re.I),
        ErrorCode.DRM_PROTECTED,
        "This media is DRM protected and cannot be processed.",
        False,
    ),
    (
        re.compile(_AGE, re.I),
        ErrorCode.AGE_RESTRICTED,
        "This media is age restricted.",
        False,
    ),
    (
        re.compile(_SIGN_IN, re.I),
        ErrorCode.AUTH_REQUIRED,
        "This media requires signing in, which is not supported.",
        False,
    ),
    (
        re.compile(_GEO, re.I),
        ErrorCode.GEO_RESTRICTED,
        "This media is not available from this location.",
        False,
    ),
    (
        re.compile(_LIVE, re.I),
        ErrorCode.LIVE_STREAM,
        "This is a live stream, which cannot be downloaded as a finished file.",
        False,
    ),
    (
        re.compile(_RATE_LIMIT, re.I),
        ErrorCode.RATE_LIMITED,
        "The source is rate limiting requests.",
        True,
    ),
    (
        re.compile(_UNAVAILABLE, re.I),
        ErrorCode.SOURCE_UNAVAILABLE,
        "This media is unavailable at that URL.",
        None,
    ),
    (
        re.compile(_NO_FORMAT, re.I),
        ErrorCode.SOURCE_UNAVAILABLE,
        "The requested format is not available for this media.",
        False,
    ),
    (
        re.compile(_NETWORK, re.I),
        ErrorCode.NETWORK_ERROR,
        "The network request failed.",
        True,
    ),
    (
        re.compile(_NO_DISK, re.I),
        ErrorCode.INSUFFICIENT_DISK,
        "There is not enough disk space to continue.",
        False,
    ),
    (
        re.compile(_NO_BINARY, re.I),
        ErrorCode.TOOL_MISSING,
        "The extraction tool is not available.",
        False,
    ),
    (
        re.compile(_BROKEN_EXTRACTOR, re.I),
        ErrorCode.TOOL_OUTDATED,
        "The extraction tool may be outdated for this site.",
        True,
    ),
]


def classify(stderr: str, *, exit_code: int | None = None) -> ExtractionError:
    """Classify a failure. Always returns an error; never raises."""
    text = stderr.strip()
    for pattern, code, message, retryable in _RULES:
        if pattern.search(text):
            return ExtractionError(code, message, detail=text or None, retryable=retryable)

    if exit_code is not None and exit_code != 0:
        return ExtractionError(
            ErrorCode.EXTRACTION_FAILED,
            "The media could not be extracted.",
            detail=text or f"exit code {exit_code}",
            retryable=False,
        )
    return ExtractionError(
        ErrorCode.EXTRACTION_FAILED,
        "The media could not be extracted.",
        detail=text or None,
        retryable=False,
    )

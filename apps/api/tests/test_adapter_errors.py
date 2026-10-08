"""yt-dlp error classification.

Exhaustive over the mapping table: an unsupported URL must never surface as a
generic failure (ENGINEERING_PRINCIPLES #16).
"""

from __future__ import annotations

import pytest

from local_media_downloader.adapters.errors import classify
from local_media_downloader.domain.errors import RETRYABLE, ErrorCode, ExtractionError


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("ERROR: Unsupported URL: https://example.com/page", ErrorCode.UNSUPPORTED_SOURCE),
        ("ERROR: [youtube] x: This video is DRM protected", ErrorCode.DRM_PROTECTED),
        ("ERROR: [youtube] x: Sign in to confirm your age", ErrorCode.AGE_RESTRICTED),
        ("ERROR: [youtube] x: Sign in to confirm you're not a bot", ErrorCode.AUTH_REQUIRED),
        ("ERROR: [youtube] x: This video is private", ErrorCode.AUTH_REQUIRED),
        (
            "ERROR: x: The uploader has not made this video available in your country",
            ErrorCode.GEO_RESTRICTED,
        ),
        ("ERROR: [youtube] x: This live event will begin in 2 hours", ErrorCode.LIVE_STREAM),
        (
            "ERROR: [youtube] x: Video unavailable. This video has been removed",
            ErrorCode.SOURCE_UNAVAILABLE,
        ),
        ("ERROR: [youtube] x: Requested format is not available", ErrorCode.SOURCE_UNAVAILABLE),
        (
            "ERROR: unable to download video data: <urlopen error timed out>",
            ErrorCode.NETWORK_ERROR,
        ),
        ("ERROR: [youtube] x: Read timed out. Retrying", ErrorCode.NETWORK_ERROR),
        (
            "ERROR: unable to download API page: HTTP Error 429: Too Many Requests",
            ErrorCode.RATE_LIMITED,
        ),
        ("ERROR: Could not write to data: No space left on device", ErrorCode.INSUFFICIENT_DISK),
        # TikTok soft-blocks a client IP for a given post; a retry later may work.
        (
            "ERROR: [tiktok] 123: Your IP address is blocked from accessing this post",
            ErrorCode.SOURCE_UNAVAILABLE,
        ),
        ("ERROR: python: [Errno 2] No such file or directory: 'yt-dlp'", ErrorCode.TOOL_MISSING),
        ("ERROR: Unable to download webpage: extractor error", ErrorCode.TOOL_OUTDATED),
        # glibc DNS wording (Linux): same unresolvable host as Winsock's
        # "getaddrinfo failed" — must stay NETWORK_ERROR, never TOOL_OUTDATED,
        # even though the line also says "Unable to download webpage".
        (
            "ERROR: Unable to download webpage: <urlopen error [Errno -2] "
            "Name or service not known>",
            ErrorCode.NETWORK_ERROR,
        ),
        (
            "ERROR: Unable to download webpage: HTTPSConnectionPool: "
            "Failed to resolve 'lmd-smoke.invalid'",
            ErrorCode.NETWORK_ERROR,
        ),
    ],
)
def test_known_failures_are_classified(stderr: str, expected: ErrorCode) -> None:
    assert classify(stderr, exit_code=1).code is expected


def test_unknown_failure_is_not_retryable_and_keeps_detail() -> None:
    error = classify("ERROR: something nobody has ever seen before", exit_code=2)
    assert error.code is ErrorCode.EXTRACTION_FAILED
    assert error.retryable is False
    assert error.detail is not None
    assert "nobody has ever seen" in error.detail


def test_network_failures_are_retryable() -> None:
    assert classify("ERROR: <urlopen error timed out>", exit_code=1).retryable is True


def test_unsupported_source_is_not_retryable() -> None:
    error = classify("ERROR: Unsupported URL: https://example.com", exit_code=1)
    assert error.retryable is False


def test_empty_stderr_with_failure_exit_code() -> None:
    error = classify("", exit_code=1)
    assert error.code is ErrorCode.EXTRACTION_FAILED
    assert error.detail == "exit code 1"


def test_classify_never_raises() -> None:
    for stderr in ("", "\x00binary\xff", "ERROR:" * 500):
        assert isinstance(classify(stderr, exit_code=1), ExtractionError)


def test_retryable_codes_are_declared_consistently() -> None:
    for code in RETRYABLE:
        assert code in set(ErrorCode)


def test_error_message_is_user_facing_and_detail_is_not_leaked() -> None:
    error = classify("ERROR: Unsupported URL: https://secret.example/x", exit_code=1)
    assert "secret.example" not in error.message
    assert "secret.example" in (error.detail or "")
    assert str(error).startswith("[UNSUPPORTED_SOURCE]")

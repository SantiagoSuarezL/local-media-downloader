"""URL admission policy.

A malicious page must never be able to turn the local service into a command
execution path (PRD security requirements), so the scheme allowlist is tested
exhaustively.
"""

from __future__ import annotations

import pytest

from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.urls import validate_url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc",
        "http://example.com/video.mp4",
        "https://example.com:8443/a/b?c=d#e",
    ],
)
def test_accepts_http_and_https(url: str) -> None:
    assert validate_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Windows/System32/cmd.exe",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "ftp://example.com/file",
        "smb://server/share",
        "gopher://example.com",
    ],
)
def test_rejects_non_http_schemes(url: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        validate_url(url)
    assert exc.value.code is ErrorCode.UNSUPPORTED_PROTOCOL
    assert exc.value.retryable is False


@pytest.mark.parametrize(
    "url", ["", "   ", "not-a-url", "example.com/video", "//example.com/video"]
)
def test_rejects_malformed_input(url: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        validate_url(url)
    assert exc.value.code is ErrorCode.INVALID_URL


def test_rejects_scheme_without_host() -> None:
    with pytest.raises(ExtractionError) as exc:
        validate_url("https:///no-host")
    assert exc.value.code is ErrorCode.INVALID_URL


def test_strips_surrounding_whitespace() -> None:
    assert validate_url("  https://example.com/v  ") == "https://example.com/v"


def test_scheme_check_is_case_insensitive() -> None:
    assert validate_url("HTTPS://example.com/v") == "HTTPS://example.com/v"


def test_localhost_urls_are_allowed_for_loopback_content() -> None:
    assert validate_url("http://127.0.0.1:8080/local.mp4") == "http://127.0.0.1:8080/local.mp4"

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


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080/local.mp4",
        "http://localhost:8765/api/v1/jobs",
        "http://[::1]:8765/",
        "http://192.168.0.10/nas/file.mp4",
        "http://10.1.2.3/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://nas.local/file.mp4",
    ],
)
def test_rejects_loopback_and_private_sources(url: str) -> None:
    """Phase 10 reversed the Phase 1 decision.

    Loopback and private addresses used to be allowed so a media file served by
    a local server could be downloaded. That makes the downloader an SSRF proxy
    into the user's own machine and LAN (metadata endpoints included), which is
    a worse trade than telling the user the source is blocked.
    """
    with pytest.raises(ExtractionError) as exc:
        validate_url(url)
    assert exc.value.code is ErrorCode.BLOCKED_SOURCE
    assert exc.value.retryable is False


def test_rejects_embedded_credentials() -> None:
    with pytest.raises(ExtractionError) as exc:
        validate_url("https://user:hunter2@example.com/private.mp4")
    assert exc.value.code is ErrorCode.INVALID_URL

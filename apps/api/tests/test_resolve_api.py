"""Resolve endpoint contract.

The extractor is stubbed so these tests never touch the network; the live
adapter is covered by the opt-in network test in ``test_ytdlp_live.py``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import serving
from local_media_downloader.adapters.normalize import normalize
from local_media_downloader.app import create_app
from local_media_downloader.config import Settings
from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.media import MediaInfo
from local_media_downloader.services.resolve import ResolveService, error_response

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


class StubExtractor:
    """Implements the Extractor port without touching yt-dlp."""

    name = "stub"
    version = "0.0.0"

    def __init__(self, error: ExtractionError | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def resolve(self, url: str, *, timeout: float) -> MediaInfo:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        raw = json.loads((FIXTURES / "yt_dlp_video.json").read_text(encoding="utf-8"))
        return normalize(raw, requested_url=url)


@pytest.fixture
def stub_extractor() -> StubExtractor:
    return StubExtractor()


@pytest.fixture
def client(tmp_path, monkeypatch, stub_extractor: StubExtractor) -> Iterator[TestClient]:
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    app = create_app(Settings.from_env(), extractor_factory=lambda: stub_extractor)
    with serving(app) as c:
        yield c


@pytest.fixture
def failing_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    error = ExtractionError(ErrorCode.UNSUPPORTED_SOURCE, "This site is not supported.")
    app = create_app(Settings.from_env(), extractor_factory=lambda: StubExtractor(error))
    with serving(app) as c:
        yield c


def test_resolve_returns_normalized_media_info(client: TestClient) -> None:
    body = client.post("/api/v1/resolve", json={"url": URL}).json()
    assert body["source"]["extractor"] == "youtube"
    assert body["duration_seconds"] == 212.0
    assert body["is_live"] is False
    assert len(body["formats"]) == 4
    assert body["formats"][0]["kind"] in {"video", "audio", "combined"}


def test_resolve_never_returns_raw_extractor_internals(client: TestClient) -> None:
    body = client.post("/api/v1/resolve", json={"url": URL}).json()
    raw_keys = {"vcodec", "acodec", "tbr", "abr", "format_note", "webpage_url", "extractor_key"}
    formats = body["formats"]
    source = body["source"]
    assert isinstance(formats, list)
    assert isinstance(source, dict)
    assert raw_keys.isdisjoint(formats[0])
    assert raw_keys.isdisjoint(source)


def test_resolve_requires_a_url(client: TestClient) -> None:
    response = client.post("/api/v1/resolve", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_resolve_rejects_empty_url(client: TestClient) -> None:
    assert client.post("/api/v1/resolve", json={"url": ""}).status_code == 422


def test_resolve_rejects_non_http_protocols(client: TestClient) -> None:
    response = client.post("/api/v1/resolve", json={"url": "file:///C:/Windows/System32/cmd.exe"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_PROTOCOL"


def test_classified_failures_return_the_domain_code(failing_client: TestClient) -> None:
    response = failing_client.post("/api/v1/resolve", json={"url": "https://example.com/x"})
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "UNSUPPORTED_SOURCE",
        "message": "This site is not supported.",
        "retryable": False,
    }


def test_error_detail_is_not_leaked_to_the_client(failing_client: TestClient) -> None:
    body = failing_client.post("/api/v1/resolve", json={"url": "https://example.com/x"}).text
    assert "Traceback" not in body
    assert set(
        failing_client.post("/api/v1/resolve", json={"url": "https://example.com/x"}).json()[
            "error"
        ]
    ) == {
        "code",
        "message",
        "retryable",
    }


def test_error_response_status_mapping() -> None:
    for code, expected in [
        (ErrorCode.INVALID_URL, 400),
        (ErrorCode.UNSUPPORTED_PROTOCOL, 400),
        (ErrorCode.UNSUPPORTED_SOURCE, 422),
        (ErrorCode.TOOL_MISSING, 503),
        (ErrorCode.INSUFFICIENT_DISK, 507),
        (ErrorCode.RATE_LIMITED, 429),
        (ErrorCode.NETWORK_ERROR, 502),
        (ErrorCode.TIMEOUT, 504),
    ]:
        status, payload = error_response(ExtractionError(code, "x"))
        assert status == expected, code
        assert payload["error"]["code"] == code.value  # type: ignore[index]


def test_error_response_includes_retryable_flag() -> None:
    _status, payload = error_response(ExtractionError(ErrorCode.NETWORK_ERROR, "x"))
    assert payload["error"]["retryable"] is True  # type: ignore[index]


def test_service_delegates_to_the_port() -> None:
    extractor = StubExtractor()
    info = ResolveService(extractor).resolve(URL)
    assert extractor.calls == [URL]
    assert info.id == "dQw4w9WgXcQ"


def test_service_propagates_classified_errors() -> None:
    extractor = StubExtractor(ExtractionError(ErrorCode.UNSUPPORTED_SOURCE, "nope"))
    with pytest.raises(ExtractionError):
        ResolveService(extractor).resolve(URL)

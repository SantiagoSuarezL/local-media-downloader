"""API contract tests: response shapes and error-code mapping.

These tests pin the exact JSON the dashboard and the extension rely on, so a
backend change that renames, drops or adds a top-level key fails loudly here
instead of breaking the UI at runtime. They are the backend half of the
contract; the frontend half lives in ``apps/web/tests/schemas.test.ts``
(Zod ``.strict()`` schemas over the same payloads).

Rule: every ``ErrorCode`` must map to an explicit HTTP status (Regla de Oro
10.1 generalized). The ``500`` default in ``error_response`` exists only for
genuinely unclassified codes; no ``ErrorCode`` member may fall through to it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import serving
from local_media_downloader.app import create_app
from local_media_downloader.config import Settings
from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.media import MediaInfo
from local_media_downloader.services.resolve import _STATUS_BY_CODE, error_response

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

INTENT = {
    "media": "video",
    "quality": "best",
    "container": "mp4",
    "audio": "include",
    "video_codec": "source",
    "processing": {"resize": None, "trim": None},
}

JOB_KEYS = {
    "id",
    "state",
    "created_at",
    "updated_at",
    "source_url",
    "title",
    "progress",
    "current_stage",
    "error_code",
    "error_message",
    "output_path",
    "priority",
    "attempt_count",
}

SETTINGS_KEYS = {
    "host",
    "port",
    "log_level",
    "data_dir",
    "database_path",
    "scheduler_max_active",
    "scheduler_max_downloads",
    "scheduler_max_encoders",
    "scheduler_max_attempts",
    "scheduler_retry_backoff_seconds",
    "output_root",
    "output_rule",
    "source_url_retention",
    "history_retention_days",
    "temporary_retention_hours",
    "bandwidth_limit_bps",
}

HEALTH_KEYS = {"status", "version", "api", "database", "storage", "tools", "extractor"}

CLEANUP_KEYS = {"urls_redacted", "jobs_deleted", "directories_deleted", "errors"}

MEDIA_INFO_KEYS = {
    "id",
    "source",
    "duration_seconds",
    "thumbnail_url",
    "is_live",
    "formats",
    "warnings",
}

MEDIA_SOURCE_KEYS = {"url", "extractor", "title", "uploader"}

MEDIA_FORMAT_KEYS = {
    "id",
    "kind",
    "container",
    "extension",
    "video_codec",
    "audio_codec",
    "width",
    "height",
    "fps",
    "bitrate",
    "audio_bitrate",
    "filesize",
    "filesize_approx",
    "dynamic_range",
    "protocol",
    "has_video",
    "has_audio",
    "quality_score",
    "note",
}

# Codes caused by the user (bad input, unavailable source, bad intent or bad
# output). These must never surface as 500 "internal error".
_USER_CAUSED = {
    ErrorCode.INVALID_URL,
    ErrorCode.UNSUPPORTED_PROTOCOL,
    ErrorCode.BLOCKED_SOURCE,
    ErrorCode.UNSUPPORTED_SOURCE,
    ErrorCode.SOURCE_UNAVAILABLE,
    ErrorCode.GEO_RESTRICTED,
    ErrorCode.AGE_RESTRICTED,
    ErrorCode.AUTH_REQUIRED,
    ErrorCode.DRM_PROTECTED,
    ErrorCode.LIVE_STREAM,
    ErrorCode.UNSUPPORTED_INTENT,
    ErrorCode.VALIDATION_FAILED,
}


class StubExtractor:
    """Implements the Extractor port without touching yt-dlp."""

    name = "stub"
    version = "0.0.0"

    def resolve(self, url: str, *, timeout: float) -> MediaInfo:
        from local_media_downloader.adapters.normalize import normalize

        raw = json.loads((FIXTURES / "yt_dlp_video.json").read_text(encoding="utf-8"))
        return normalize(raw, requested_url=url)


class NoopExecutor:
    """Executor that never finishes: the job stays non-terminal.

    The in-process scheduler dispatches every QUEUED job within ~50 ms, so
    without this stub a created job would run the real yt-dlp download (a
    network call inside a contract test) and could even reach COMPLETED
    before the duplicate POST arrives, making the dedupe assertion flaky.
    Waiting on the cooperative cancel event keeps the job in flight; the
    scheduler shutdown at teardown cancels it cleanly (→ CANCELLED).
    """

    async def run(self, job, plan, cancel) -> None:  # type: ignore[no-untyped-def]
        from local_media_downloader.services.executor import JobCancelled

        await cancel.wait()
        raise JobCancelled()


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    app = create_app(
        Settings.from_env(),
        extractor_factory=StubExtractor,
        executor_factory=NoopExecutor,
    )
    with serving(app) as c:
        yield c


def test_every_error_code_maps_to_an_explicit_status() -> None:
    """No ErrorCode may fall through to the 500 default (Ref: Regla 10.1)."""
    unmapped = [code for code in ErrorCode if code not in _STATUS_BY_CODE]
    assert not unmapped, f"ErrorCodes without an HTTP status (would return 500): {unmapped}"


def test_user_caused_errors_never_return_5xx() -> None:
    for code in _USER_CAUSED:
        status, payload = error_response(ExtractionError(code, "x"))
        assert 400 <= status < 500, f"{code.value} maps to {status}"
        assert payload["error"]["code"] == code.value  # type: ignore[index]


def test_error_envelope_shape() -> None:
    _status, payload = error_response(ExtractionError(ErrorCode.NETWORK_ERROR, "boom"))
    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "retryable"}  # type: ignore[union-attr]


def test_service_root_contract(client: TestClient) -> None:
    body = client.get("/api/v1").json()
    assert set(body) == {"service", "health"}
    assert body["health"] == "/api/v1/health"


def test_health_contract(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    assert set(body) == HEALTH_KEYS
    assert set(body["database"]) == {"status", "detail"}
    assert set(body["storage"]) == {"status", "detail"}
    assert set(body["extractor"]) == {"name", "available", "version", "may_be_outdated"}
    for tool in body["tools"].values():
        assert set(tool) == {"detected", "version"}


def test_settings_contract(client: TestClient) -> None:
    body = client.get("/api/v1/settings").json()
    assert set(body) == SETTINGS_KEYS


def test_resolve_contract(client: TestClient) -> None:
    body = client.post("/api/v1/resolve", json={"url": URL}).json()
    assert set(body) == MEDIA_INFO_KEYS
    assert set(body["source"]) == MEDIA_SOURCE_KEYS
    assert body["formats"], "the fixture must resolve at least one format"
    for fmt in body["formats"]:
        assert set(fmt) == MEDIA_FORMAT_KEYS, f"format keys drifted: {sorted(fmt)}"


def test_create_job_contract(client: TestClient) -> None:
    response = client.post("/api/v1/jobs", json={"url": URL, "intent": INTENT})
    assert response.status_code == 201
    assert set(response.json()) == JOB_KEYS


@pytest.mark.parametrize("container", ["gif", "webp", "sticker", "mobile"])
def test_preset_job_contract(client: TestClient, container: str) -> None:
    intent = {
        **INTENT,
        "container": container,
        "audio": "include" if container == "mobile" else "remove",
    }
    response = client.post("/api/v1/jobs", json={"url": URL, "intent": intent})
    assert response.status_code == 201
    assert set(response.json()) == JOB_KEYS


def test_duplicate_job_contract(client: TestClient) -> None:
    payload = {"url": URL, "intent": INTENT}
    first = client.post("/api/v1/jobs", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/jobs", json=payload)
    assert second.status_code == 200
    body = second.json()
    assert body["duplicate"] is True
    assert set(body) == JOB_KEYS | {"duplicate"}
    assert body["id"] == first.json()["id"]


def test_job_list_contract(client: TestClient) -> None:
    client.post("/api/v1/jobs", json={"url": URL, "intent": INTENT})
    body = client.get("/api/v1/jobs", params={"limit": 10}).json()
    assert set(body) == {"jobs", "next_cursor"}
    assert len(body["jobs"]) == 1
    assert set(body["jobs"][0]) == JOB_KEYS


def test_batch_contract(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs/batch",
        json={"items": [{"url": URL, "intent": INTENT}]},
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"results"}
    (result,) = body["results"]
    assert set(result) == {"index", "status", "job"}
    assert set(result["job"]) == {"id", "state", "title", "priority"}


def test_cleanup_contract(client: TestClient) -> None:
    response = client.post("/api/v1/maintenance/cleanup")
    assert response.status_code == 200
    assert set(response.json()) == CLEANUP_KEYS


def test_error_responses_share_one_envelope(client: TestClient) -> None:
    """Every error path returns {"error": {"code", "message"}} — never HTML."""
    probes = [
        ("GET", "/api/v1/nope", None),
        ("POST", "/api/v1/resolve", {"url": ""}),
        ("GET", "/api/v1/jobs/does-not-exist", None),
        ("POST", "/api/v1/jobs/does-not-exist/cancel", None),
        ("POST", "/api/v1/jobs/does-not-exist/retry", None),
    ]
    for method, path, payload in probes:
        response = client.request(method, path, json=payload)
        assert response.status_code >= 400, (method, path)
        body = response.json()
        assert set(body) == {"error"}, (method, path, body)
        assert set(body["error"]) >= {"code", "message"}, (method, path, body)

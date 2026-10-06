"""Security hardening acceptance tests (Phase 10).

Covers the plan's list of attempts plus the controls added around them:
loopback bind, Host/Origin (DNS rebinding), token auth, request size, resolve
rate limit, SSRF guard, output path containment and secret redaction.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import LOOPBACK_BASE_URL, serving
from local_media_downloader.adapters.normalize import normalize
from local_media_downloader.app import TOKEN_COOKIE, create_app
from local_media_downloader.config import Settings
from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.filenames import output_path_for, sanitize_filename
from local_media_downloader.domain.media import MediaInfo, MediaSource
from local_media_downloader.domain.urls import validate_url
from local_media_downloader.logging_config import _JsonFormatter, register_secret
from local_media_downloader.security import (
    TOKEN_HEADER,
    SecurityError,
    assert_loopback_host,
    token_matches,
    validate_host,
    validate_origin,
)

FIXTURES = Path(__file__).parent / "fixtures"
VIDEO_URL = "https://www.youtube.com/watch?v=abc"


class StubExtractor:
    name = "stub"
    version = "0.0.0"

    def resolve(self, url: str, *, timeout: float) -> MediaInfo:
        return MediaInfo(
            source=MediaSource(
                url=url,
                extractor="stub",
                extractor_key="stub",
                title="stub",
                uploader=None,
            ),
            id="1",
            duration_seconds=None,
            thumbnail_url=None,
            is_live=False,
            formats=(),
            warnings=(),
        )


class FixtureExtractor(StubExtractor):
    """Same stub, but with real formats so a job can actually be created."""

    def resolve(self, url: str, *, timeout: float) -> MediaInfo:
        raw = json.loads((FIXTURES / "yt_dlp_video.json").read_text(encoding="utf-8"))
        return normalize(raw, requested_url=url)


@pytest.fixture
def settings_env(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    return Settings.from_env()


@pytest.fixture
def client(settings_env: Settings) -> Iterator[TestClient]:
    with serving(create_app(settings_env, extractor_factory=StubExtractor)) as c:
        yield c


# --- bind -------------------------------------------------------------------


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "::", "example.com"])
def test_non_loopback_bind_is_refused(host: str) -> None:
    with pytest.raises(SecurityError) as exc:
        assert_loopback_host(host)
    assert exc.value.code == "NON_LOOPBACK_BIND"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_loopback_bind_is_allowed(host: str) -> None:
    assert_loopback_host(host)


# --- Host / Origin (DNS rebinding) -----------------------------------------


@pytest.mark.parametrize("host_header", [None, "", "evil.example.com", "127.0.0.1.evil.com"])
def test_non_loopback_host_is_rejected(host_header: str | None) -> None:
    with pytest.raises(SecurityError):
        validate_host(host_header)


def test_wrong_port_is_rejected() -> None:
    with pytest.raises(SecurityError):
        validate_host("127.0.0.1:9999", expected_port=8765)


@pytest.mark.parametrize("origin", ["https://evil.example.com", "null", "http://192.168.0.5:8765"])
def test_cross_origin_is_rejected(origin: str) -> None:
    with pytest.raises(SecurityError):
        validate_origin(origin)


@pytest.mark.parametrize("origin", [None, "http://127.0.0.1:8765", "http://localhost:8765"])
def test_loopback_or_absent_origin_is_allowed(origin: str | None) -> None:
    validate_origin(origin)


def test_dns_rebinding_request_is_refused_at_the_boundary(settings_env: Settings) -> None:
    """A page at evil.com resolving to 127.0.0.1 still sends its own Host."""
    app = create_app(settings_env, extractor_factory=StubExtractor)
    with serving(app, base_url="http://evil.example.com") as c:
        response = c.get("/api/v1/jobs")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "INVALID_HOST"
        # Even the shell refuses: no token is handed to a rebound host.
        assert c.get("/").status_code == 403


def test_cross_origin_post_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/v1/resolve", json={"url": VIDEO_URL}, headers={"Origin": "https://evil.example.com"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_ORIGIN"


# --- token ------------------------------------------------------------------


def test_api_requires_a_token(settings_env: Settings) -> None:
    app = create_app(settings_env, extractor_factory=StubExtractor)
    with serving(app) as c:
        # `serving` authenticates; drop it to simulate another local process.
        c.headers.pop(TOKEN_HEADER)
        c.cookies.clear()
        for path in ("/api/v1/jobs", "/api/v1/settings"):
            response = c.get(path)
            assert response.status_code == 401, path
            assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_health_stays_public_for_the_extension(settings_env: Settings) -> None:
    app = create_app(settings_env, extractor_factory=StubExtractor)
    with serving(app) as c:
        c.headers.pop(TOKEN_HEADER)
        c.cookies.clear()
        assert c.get("/api/v1/health").status_code == 200


def test_cookie_authenticates_browser_clients(settings_env: Settings, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><head><title>LMD</title></head>")
    settings = Settings(data_dir=settings_env.data_dir, web_dist=dist)
    app = create_app(settings, extractor_factory=StubExtractor)
    with serving(app) as c:
        shell = c.get("/")
        assert shell.status_code == 200
        # The shell hands the token over only after the Host check passed.
        assert TOKEN_COOKIE in c.cookies
        c.headers.pop(TOKEN_HEADER)
        assert c.get("/api/v1/jobs").status_code == 200


def test_token_is_stable_across_restarts(settings_env: Settings) -> None:
    app = create_app(settings_env, extractor_factory=StubExtractor)
    with serving(app):
        first = app.state.token
    second_app = create_app(settings_env, extractor_factory=StubExtractor)
    with serving(second_app):
        assert second_app.state.token == first


def test_token_comparison_rejects_wrong_values() -> None:
    assert token_matches("abc", "abc")
    assert not token_matches("abc", "abd")
    assert not token_matches(None, "abc")
    assert not token_matches("", "abc")


def test_token_is_never_written_to_logs(settings_env: Settings, capsys) -> None:
    app = create_app(settings_env, extractor_factory=StubExtractor)
    with serving(app) as c:
        token = app.state.token
        c.get("/api/v1/jobs")
    captured = capsys.readouterr()
    assert token not in captured.err


def test_redaction_masks_registered_secrets() -> None:
    secret = "super-secret-token-value"
    register_secret(secret)
    assert secret not in _JsonFormatter().format(_record(secret))


def _record(message: str):  # type: ignore[no-untyped-def]
    import logging

    record = logging.LogRecord("test", logging.INFO, __file__, 1, message, (), None)
    record.component = "test"
    return record


# --- request size -----------------------------------------------------------


def test_oversized_body_is_refused(settings_env: Settings) -> None:
    small = Settings(
        data_dir=settings_env.data_dir,
        web_dist=settings_env.web_dist,
        max_request_bytes=256,
    )
    with serving(create_app(small, extractor_factory=StubExtractor)) as c:
        response = c.post("/api/v1/jobs", json={"url": VIDEO_URL, "intent": {"x": "y" * 4096}})
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_oversized_url_field_is_refused(client: TestClient) -> None:
    response = client.post("/api/v1/resolve", json={"url": f"https://e.com/{'a' * 5000}"})
    assert response.status_code == 422


# --- rate limit -------------------------------------------------------------


def test_resolve_is_rate_limited(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    monkeypatch.setenv("LMD_RESOLVE_RATE_LIMIT", "2")
    settings = Settings.from_env()
    with serving(create_app(settings, extractor_factory=StubExtractor)) as c:
        assert c.post("/api/v1/resolve", json={"url": VIDEO_URL}).status_code == 200
        assert c.post("/api/v1/resolve", json={"url": VIDEO_URL}).status_code == 200
        limited = c.post("/api/v1/resolve", json={"url": VIDEO_URL})
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "RATE_LIMITED"
        assert int(limited.headers["Retry-After"]) >= 1


# --- SSRF / URL policy ------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Windows/System32/cmd.exe",
        "../../../../etc/passwd",
        "data:text/html,<script>alert(1)</script>",
        "javascript:alert(1)",
        "http://127.0.0.1:8765/api/v1/jobs",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
def test_dangerous_urls_are_rejected(url: str) -> None:
    with pytest.raises(ExtractionError):
        validate_url(url)


def test_arbitrary_command_strings_never_reach_a_shell(settings_env: Settings) -> None:
    """Intent has no free-text field, so an injection attempt fails validation."""
    with serving(create_app(settings_env, extractor_factory=FixtureExtractor)) as c:
        response = c.post(
            "/api/v1/jobs",
            json={
                "url": VIDEO_URL,
                "intent": {
                    "media": "video; rm -rf /",
                    "quality": "best",
                    "container": "mp4",
                    "audio": "include",
                    "video_codec": "source",
                },
            },
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_INTENT"


def test_user_errors_are_not_reported_as_server_errors() -> None:
    """A bad dropdown choice must not become a 500 (Phase 10 status mapping)."""
    from local_media_downloader.services.resolve import error_response

    for code in (
        ErrorCode.UNSUPPORTED_INTENT,
        ErrorCode.VALIDATION_FAILED,
        ErrorCode.BLOCKED_SOURCE,
    ):
        status, _ = error_response(ExtractionError(code, "x"))
        assert 400 <= status < 500, code


# --- filenames / output containment ----------------------------------------


@pytest.mark.parametrize(
    ("title", "expected_fragment"),
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\system32", "windows"),
        ("C:\\Windows\\System32\\evil", "Windows"),
        ("normal title", "normal title"),
        ("   ", None),
        ("...", "download"),
        ("CON", "CON-file"),
        ("bad\x00name", "bad name"),
    ],
)
def test_sanitize_filename_never_escapes(title: str, expected_fragment: str | None) -> None:
    result = sanitize_filename(title, fallback="download", extension="mp4")
    assert "/" not in result and "\\" not in result
    assert result.endswith(".mp4")
    if expected_fragment is None:
        assert result == "download.mp4"
    else:
        assert expected_fragment in result


def test_output_path_stays_inside_the_job_directory(tmp_path: Path) -> None:
    base = tmp_path / "output"
    base.mkdir()
    path = output_path_for(base, "../../escape", fallback="job", extension="mp4")
    assert path.parent == base.resolve()


def test_output_path_refuses_to_leave_the_directory(tmp_path: Path) -> None:
    """Containment is proven, not assumed: a sanitizer regression cannot escape."""
    base = tmp_path / "output"
    base.mkdir()
    from local_media_downloader.domain import filenames

    original = filenames.sanitize_filename
    try:
        filenames.sanitize_filename = lambda *a, **k: "../escaped.mp4"  # type: ignore[assignment]
        with pytest.raises(ValueError):
            filenames.output_path_for(base, "title", fallback="job", extension="mp4")
    finally:
        filenames.sanitize_filename = original  # type: ignore[assignment]


def test_api_never_accepts_an_output_path(settings_env: Settings) -> None:
    """The output root is server-owned: the create payload has no such field."""
    with serving(create_app(settings_env, extractor_factory=FixtureExtractor)) as c:
        response = c.post(
            "/api/v1/jobs",
            json={
                "url": VIDEO_URL,
                "output_path": "/etc/passwd",
                "intent": {
                    "media": "video",
                    "quality": "best",
                    "container": "mp4",
                    "audio": "include",
                    "video_codec": "source",
                },
            },
        )
        assert response.status_code == 201
        assert response.json()["output_path"] is None


# --- subprocess invocation --------------------------------------------------


def test_tool_invocations_are_argument_arrays() -> None:
    """No `shell=True` anywhere: arguments can never be re-parsed by a shell."""
    import pathlib

    adapters = pathlib.Path(__file__).resolve().parents[1] / "src/local_media_downloader"
    offenders = [
        path.name
        for path in adapters.rglob("*.py")
        if "shell=True" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_token_table_entry_is_not_readable_through_the_api(settings_env: Settings) -> None:
    app = create_app(settings_env, extractor_factory=StubExtractor)
    with serving(app) as c:
        body = c.get("/api/v1/settings").text
        assert "auth_token" not in body
        assert app.state.token not in body


def test_health_probe_is_cached(settings_env: Settings) -> None:
    """Unauthenticated health must not spawn five subprocesses per call."""
    app = create_app(settings_env, extractor_factory=StubExtractor)
    with serving(app) as c:
        c.headers.pop(TOKEN_HEADER)
        first = c.get("/api/v1/health").json()
        second = c.get("/api/v1/health").json()
        assert first == second


def test_base_url_is_loopback_for_tests() -> None:
    assert LOOPBACK_BASE_URL.startswith("http://127.0.0.1")

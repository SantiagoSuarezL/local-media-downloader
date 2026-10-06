from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from conftest import serving
from local_media_downloader.app import create_app
from local_media_downloader.config import Settings


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    # Hermetic: never mount a developer's real apps/web/dist into the tests.
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    settings = Settings.from_env()
    with serving(create_app(settings)) as test_client:
        yield test_client


def test_health_reports_versions_and_statuses(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()

    assert body["api"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["status"] == "ok"

    assert body["database"]["status"] == "ok"
    assert body["database"]["detail"].startswith("ok (schema v")
    assert body["storage"]["status"] == "ok"

    tools = body["tools"]
    for name in ("yt_dlp", "yt_dlp_ejs", "deno", "ffmpeg", "ffprobe"):
        assert name in tools
        assert set(tools[name]) == {"detected", "version"}
        if tools[name]["detected"]:
            assert isinstance(tools[name]["version"], str)


def test_health_does_not_leak_filesystem_paths(client: TestClient) -> None:
    payload = json.dumps(client.get("/api/v1/health").json())
    assert "data_dir" not in payload
    assert "app.db" not in payload


def test_unknown_route_uses_structured_error(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_service_root_points_to_health(client: TestClient) -> None:
    assert client.get("/api/v1").json()["health"] == "/api/v1/health"


def test_settings_endpoint_reports_runtime_configuration(client: TestClient) -> None:
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["host"] == "127.0.0.1"
    assert body["port"] == 8765
    assert set(body) == {
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
    }


def test_web_ui_is_served_when_a_build_exists(tmp_path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "assets" / "app.js").write_text("console.log('ui')")
    (dist / "index.html").write_text("<!doctype html><head><title>LMD</title></head>")
    settings = Settings(data_dir=tmp_path / "data", web_dist=dist)

    with serving(create_app(settings)) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "<title>LMD</title>" in root.text
        # deep links render the SPA shell, unknown API routes stay JSON 404
        assert client.get("/history").status_code == 200
        assert client.get("/api/v1/nope").json()["error"]["code"] == "NOT_FOUND"
        assert client.get("/assets/app.js").status_code == 200


def test_startup_creates_the_database_file(client: TestClient, tmp_path) -> None:
    assert (tmp_path / "data" / "app.db").exists()


def test_responses_are_never_cacheable(client: TestClient) -> None:
    """Loopback service with live state: an intermediary cache would show a
    stale job, contradicting the SSE progress stream. No CDN exists here."""
    for path in ("/", "/api/v1/health", "/api/v1/nope"):
        response = client.get(path)
        assert response.headers["Cache-Control"] == "no-store", path

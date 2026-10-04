from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from local_media_downloader.app import create_app
from local_media_downloader.config import Settings


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    settings = Settings.from_env()
    with TestClient(create_app(settings)) as test_client:
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
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}


def test_root_points_to_health(client: TestClient) -> None:
    assert client.get("/").json()["health"] == "/api/v1/health"


def test_startup_creates_the_database_file(client: TestClient, tmp_path) -> None:
    assert (tmp_path / "data" / "app.db").exists()

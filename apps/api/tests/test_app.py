from __future__ import annotations

import json

from fastapi.testclient import TestClient

from local_media_downloader.app import create_app
from local_media_downloader.config import Settings


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    settings = Settings.from_env()
    return TestClient(create_app(settings))


def test_health_reports_versions_and_statuses(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()

    assert body["api"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["status"] == "ok"

    database = body["database"]
    assert database["status"] == "ok"

    storage = body["storage"]
    assert storage["status"] == "ok"

    tools = body["tools"]
    for name in ("yt_dlp", "yt_dlp_ejs", "deno", "ffmpeg", "ffprobe"):
        assert name in tools
        assert set(tools[name]) == {"detected", "version"}
        if tools[name]["detected"]:
            assert isinstance(tools[name]["version"], str)


def test_health_does_not_leak_filesystem_paths(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/v1/health")
    payload = json.dumps(response.json())
    assert str(tmp_path) not in payload
    assert "data_dir" not in payload


def test_unknown_route_uses_structured_error(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}


def test_root_points_to_health(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/").json()["health"] == "/api/v1/health"

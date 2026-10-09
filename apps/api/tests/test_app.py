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
    app = create_app(settings)
    with serving(app) as test_client:
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
        "output_root",
        "output_rule",
        "source_url_retention",
        "history_retention_days",
        "temporary_retention_hours",
        "bandwidth_limit_bps",
    }


def test_settings_update_retention_policy(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/settings", json={"history_retention_days": 7, "source_url_retention": "30days"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["history_retention_days"] == 7
    assert body["source_url_retention"] == "30days"


def test_settings_update_rejects_invalid_retention(client: TestClient) -> None:
    response = client.patch("/api/v1/settings", json={"source_url_retention": "sometimes"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_settings_update_rejects_boot_configuration(client: TestClient) -> None:
    response = client.patch("/api/v1/settings", json={"host": "0.0.0.0"})
    assert response.status_code == 422


def test_cleanup_endpoint_runs_retention(client: TestClient) -> None:
    response = client.post("/api/v1/maintenance/cleanup")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"urls_redacted", "jobs_deleted", "directories_deleted", "errors"}


def _make_job(app, **kwargs):
    from local_media_downloader import jobs as repo
    from local_media_downloader.job_state import JobState

    return repo.create_job(
        app.state.db,
        source_url="https://example.com/video",
        state=kwargs.pop("state", JobState.QUEUED),
        **kwargs,
    )


def _batch_intent() -> dict[str, str]:
    return {
        "media": "video",
        "quality": "best",
        "container": "mp4",
        "audio": "include",
        "video_codec": "source",
    }


def test_batch_endpoint_reports_per_item_errors(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs/batch",
        json={
            "items": [
                {"url": "https://example.com/a", "intent": _batch_intent()},
                {"url": "not-a-url", "intent": _batch_intent()},
                {"url": "https://example.com/b", "intent": _batch_intent()},
            ]
        },
    )
    assert response.status_code == 201
    results = response.json()["results"]
    assert len(results) == 3
    assert results[0]["status"] in {"created", "duplicate", "error"}
    assert results[1]["status"] == "error"
    assert results[1]["error"]["code"] == "INVALID_URL"
    assert results[2]["status"] in {"created", "duplicate", "error"}


def test_batch_rejects_empty_items(client: TestClient) -> None:
    response = client.post("/api/v1/jobs/batch", json={"items": []})
    assert response.status_code == 422


def test_create_job_returns_duplicate_instead_of_requeueing(tmp_path, monkeypatch) -> None:
    from local_media_downloader import jobs as repo
    from local_media_downloader.app import create_app
    from local_media_downloader.config import Settings
    from local_media_downloader.domain.dedupe import dedupe_key
    from local_media_downloader.job_state import JobState

    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    settings = Settings.from_env()
    app = create_app(settings)
    with serving(app) as test_client:
        intent = dict(_batch_intent())
        url = "https://example.com/video"
        existing = repo.create_job(
            app.state.db,
            source_url=url,
            dedupe_key=dedupe_key(url, intent),
            intent_json=json.dumps(intent),
            state=JobState.QUEUED,
        )
        response = test_client.post("/api/v1/jobs", json={"url": url, "intent": intent})
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == existing.id
        assert body["duplicate"] is True


def test_retry_failed_job(tmp_path, monkeypatch) -> None:
    from local_media_downloader.app import create_app
    from local_media_downloader.config import Settings
    from local_media_downloader.job_state import JobState

    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    settings = Settings.from_env()
    app = create_app(settings)
    with serving(app) as test_client:
        from local_media_downloader import jobs as repo

        job = repo.create_job(
            app.state.db,
            source_url="https://example.com/video",
            state=JobState.QUEUED,
        )
        repo.transition(
            app.state.db,
            job.id,
            JobState.FAILED,
            error_code="NETWORK_ERROR",
        )
        response = test_client.post(f"/api/v1/jobs/{job.id}/retry")
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "RETRY_WAIT"
        assert body["attempt_count"] == 0
        assert body["error_code"] is None


def test_retry_rejects_completed_job(tmp_path, monkeypatch) -> None:
    from local_media_downloader.app import create_app
    from local_media_downloader.config import Settings
    from local_media_downloader.job_state import JobState

    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    settings = Settings.from_env()
    app = create_app(settings)
    with serving(app) as test_client:
        from local_media_downloader import jobs as repo

        job = repo.create_job(
            app.state.db,
            source_url="https://example.com/video",
            state=JobState.COMPLETED,
        )
        response = test_client.post(f"/api/v1/jobs/{job.id}/retry")
        assert response.status_code == 409


def test_priority_endpoint_changes_queue_order(tmp_path, monkeypatch) -> None:
    from local_media_downloader.app import create_app
    from local_media_downloader.config import Settings

    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LMD_WEB_DIST", str(tmp_path / "no-web-build"))
    settings = Settings.from_env()
    app = create_app(settings)
    with serving(app) as test_client:
        from local_media_downloader import jobs as repo

        job = repo.create_job(app.state.db, source_url="https://example.com/video")
        response = test_client.post(f"/api/v1/jobs/{job.id}/priority", json={"priority": 5})
        assert response.status_code == 200
        assert response.json()["priority"] == 5


def test_list_jobs_paginates_with_cursor(client: TestClient) -> None:
    response = client.get("/api/v1/jobs?limit=1")
    assert response.status_code == 200
    body = response.json()
    assert "jobs" in body
    assert "next_cursor" in body


def test_list_jobs_filters_by_state(client: TestClient) -> None:
    response = client.get("/api/v1/jobs?states=QUEUED")
    assert response.status_code == 200
    body = response.json()
    for job in body["jobs"]:
        assert job["state"] == "QUEUED"


def test_list_jobs_rejects_invalid_state_filter(client: TestClient) -> None:
    response = client.get("/api/v1/jobs?states=BOGUS")
    assert response.status_code == 422


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


def test_web_ui_serves_root_static_files_with_their_true_content_type(tmp_path) -> None:
    """Vite copies `public/` to the dist root: favicon and the self-hosted
    web fonts. Before this behaviour existed the SPA fallback answered a font
    request with the HTML shell, the browser could not parse it, and the
    dashboard silently rendered in the system stack instead of Archivo."""
    dist = tmp_path / "dist"
    (dist / "fonts").mkdir(parents=True)
    (dist / "favicon.svg").write_text("<svg xmlns=''></svg>", encoding="utf-8")
    (dist / "fonts" / "archivo-latin.woff2").write_bytes(b"wOF2 fake")
    (dist / "index.html").write_text(
        "<!doctype html><head><title>LMD</title></head>", encoding="utf-8"
    )
    settings = Settings(data_dir=tmp_path / "data", web_dist=dist)

    with serving(create_app(settings)) as client:
        favicon = client.get("/favicon.svg")
        assert favicon.status_code == 200
        assert favicon.text == "<svg xmlns=''></svg>"
        assert favicon.headers["content-type"].startswith("image/svg+xml")

        font = client.get("/fonts/archivo-latin.woff2")
        assert font.status_code == 200
        assert font.content == b"wOF2 fake"
        assert font.headers["content-type"].startswith("font/woff2")

        # The shell is the one file that must NEVER be served raw: it is the
        # only path that injects the token, so it always goes through it.
        direct = client.get("/index.html")
        assert direct.status_code == 200
        assert 'name="lmd-token"' in direct.text

        # A traversal attempt must not read anything outside the dist root.
        escape = client.get("/fonts/..%2F..%2Fpyproject.toml")
        assert escape.status_code == 200
        assert "<title>LMD</title>" in escape.text
        assert "[project]" not in escape.text


def test_startup_creates_the_database_file(client: TestClient, tmp_path) -> None:
    assert (tmp_path / "data" / "app.db").exists()


def test_responses_are_never_cacheable(client: TestClient) -> None:
    """Loopback service with live state: an intermediary cache would show a
    stale job, contradicting the SSE progress stream. No CDN exists here."""
    for path in ("/", "/api/v1/health", "/api/v1/nope"):
        response = client.get(path)
        assert response.headers["Cache-Control"] == "no-store", path

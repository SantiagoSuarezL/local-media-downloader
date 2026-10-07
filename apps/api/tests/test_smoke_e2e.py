"""Executable smoke test: a real server process, real HTTP, real SQLite file.

Unlike the rest of the suite (in-process ``TestClient``), this test boots the
production entrypoint (``python -m local_media_downloader`` → Granian) on a
fresh port with an isolated data directory, then drives it over real HTTP:

- public health vs. authenticated routes (401 without a token);
- the dashboard token handoff (``<meta name="lmd-token">`` + HttpOnly cookie);
- the HTTP status matrix for resolve / create / batch / cancel / retry /
  cleanup, including per-item batch isolation;
- persistence across a full process restart (same token, same settings table).

Hermetic by design (Regla de Oro 10.2): the port is freshly allocated, so the
test can never mistake a stale server for its own, and the data directory is
a ``tmp_path`` the server itself initializes. No network download is needed:
unresolvable ``.invalid`` URLs fail fast inside yt-dlp (DNS), which is
exactly what exercises the 5xx error mapping end to end.

Marked ``smoke`` so fast local runs can skip it: ``uv run pytest -m "not smoke"``.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from local_media_downloader.app import TOKEN_COOKIE
from local_media_downloader.security import TOKEN_HEADER

pytestmark = pytest.mark.smoke

_TOKEN_RE = re.compile(r'<meta name="lmd-token" content="([^"]+)" />')
_UNRESOLVABLE = "https://lmd-smoke.invalid/watch?v=smoke01"
_VALID_INTENT = {
    "media": "video",
    "quality": "best",
    "container": "mp4",
    "audio": "include",
    "video_codec": "source",
    "processing": {"resize": None, "trim": None},
}
_BAD_INTENT = {
    "media": "video",
    "quality": "best",
    "container": "not-a-container",
    "audio": "include",
}

_STARTUP_DEADLINE_SECONDS = 120.0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(
    *, port: int, data_dir: Path, web_dist: Path, output_root: Path, log_path: Path
) -> subprocess.Popen[str]:
    env = dict(os.environ)
    env.update(
        {
            "LMD_HOST": "127.0.0.1",
            "LMD_PORT": str(port),
            "LMD_DATA_DIR": str(data_dir),
            "LMD_WEB_DIST": str(web_dist),
            "LMD_OUTPUT_ROOT": str(output_root),
            "LMD_LOG_LEVEL": "WARNING",
            "LMD_SCHED_MAX_ATTEMPTS": "1",
            "LMD_SCHED_RETRY_BACKOFF": "0.1",
            "LMD_RESOLVE_RATE_LIMIT": "120",
        }
    )
    log_file = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "-m", "local_media_downloader"],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_server(proc: subprocess.Popen[str]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=15.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=15.0)


def _tail(log_path: Path, lines: int = 30) -> str:
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "<no server log>"
    return "\n".join(content[-lines:])


def _wait_for_health(base_url: str) -> None:
    deadline = time.monotonic() + _STARTUP_DEADLINE_SECONDS
    last_error = "no attempts"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(base_url + "/api/v1/health", timeout=5.0)
            if response.status_code == 200:
                return
            last_error = f"status {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(1.0)
    raise AssertionError(f"server did not become healthy: {last_error}")


def _fetch_token(base_url: str) -> tuple[str, str]:
    """Return (header token, cookie token) from the served shell."""
    response = httpx.get(base_url + "/", timeout=10.0)
    assert response.status_code == 200, f"shell not served: {response.status_code}"
    assert "text/html" in response.headers.get("content-type", "")
    match = _TOKEN_RE.search(response.text)
    assert match, "shell carries no lmd-token meta tag"
    cookie_token = response.cookies.get(TOKEN_COOKIE, "")
    assert cookie_token, "shell sets no lmd_token cookie"
    assert match.group(1) == cookie_token, "meta token and cookie token disagree"
    set_cookie = response.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower(), "token cookie must be HttpOnly"
    assert "samesite=strict" in set_cookie.lower().replace(" ", ""), (
        "token cookie must be SameSite=Strict"
    )
    return match.group(1), cookie_token


def test_live_server_http_contract_and_restart_persistence(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    web_dist = tmp_path / "web-dist"
    web_dist.mkdir(parents=True)
    # Minimal shell: the server injects the token after <head>, like the real build.
    (web_dist / "index.html").write_text(
        "<!doctype html><html><head></head><body></body></html>", encoding="utf-8"
    )
    log_path = tmp_path / "server.log"

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = _start_server(
        port=port,
        data_dir=data_dir,
        web_dist=web_dist,
        output_root=tmp_path / "downloads",
        log_path=log_path,
    )
    try:
        _wait_for_health(base_url)
        token, cookie_token = _fetch_token(base_url)

        authed = httpx.Client(base_url=base_url, headers={TOKEN_HEADER: token}, timeout=60.0)
        cookie_client = httpx.Client(base_url=base_url, timeout=30.0)
        cookie_client.cookies.set(TOKEN_COOKIE, cookie_token)
        anon = httpx.Client(base_url=base_url, timeout=30.0)

        # --- Authentication boundary over real HTTP ---
        assert anon.get("/api/v1/health").status_code == 200
        denied = anon.get("/api/v1/jobs")
        assert denied.status_code == 401
        assert denied.json()["error"]["code"] == "UNAUTHORIZED"
        assert authed.get("/api/v1/jobs").status_code == 200
        # The cookie path (what EventSource uses) authenticates too.
        assert cookie_client.get("/api/v1/settings").status_code == 200
        # API responses are never cached.
        assert authed.get("/api/v1/settings").headers["cache-control"] == "no-store"

        # --- Response-shape contracts over real HTTP ---
        health = anon.get("/api/v1/health").json()
        assert set(health) == {
            "status",
            "version",
            "api",
            "database",
            "storage",
            "tools",
            "extractor",
        }
        settings = authed.get("/api/v1/settings").json()
        assert settings["port"] == port
        assert settings["history_retention_days"] > 0

        # --- Runtime settings round-trip ---
        patched = authed.patch("/api/v1/settings", json={"history_retention_days": 30}).json()
        assert patched["history_retention_days"] == 30
        assert authed.patch("/api/v1/settings", json={"port": 9999}).status_code == 422
        bad_value = authed.patch("/api/v1/settings", json={"source_url_retention": "forever"})
        assert bad_value.status_code == 422

        # --- Status matrix: resolve ---
        assert authed.post("/api/v1/resolve", json={}).status_code == 422
        proto = authed.post("/api/v1/resolve", json={"url": "file:///etc/passwd"})
        assert proto.status_code == 400
        assert proto.json()["error"]["code"] == "UNSUPPORTED_PROTOCOL"
        failed = authed.post("/api/v1/resolve", json={"url": _UNRESOLVABLE})
        assert failed.status_code in {502, 504}, failed.text
        envelope = failed.json()
        assert set(envelope) == {"error"}
        assert set(envelope["error"]) == {"code", "message", "retryable"}

        # --- Status matrix: create (intent validated before any tool runs) ---
        bad_intent = authed.post("/api/v1/jobs", json={"url": _UNRESOLVABLE, "intent": _BAD_INTENT})
        assert bad_intent.status_code == 422
        assert bad_intent.json()["error"]["code"] == "UNSUPPORTED_INTENT"
        # Unresolvable source: the failure surfaces as 5xx, and no job row exists.
        unresolvable = authed.post(
            "/api/v1/jobs", json={"url": _UNRESOLVABLE, "intent": _VALID_INTENT}
        )
        assert unresolvable.status_code in {502, 504}, unresolvable.text
        listed = authed.get("/api/v1/jobs", params={"limit": 10}).json()
        assert listed == {"jobs": [], "next_cursor": None}

        # --- Batch isolates per-item failures, in input order ---
        batch = authed.post(
            "/api/v1/jobs/batch",
            json={
                "items": [
                    {"url": "file:///etc/passwd", "intent": _VALID_INTENT},
                    {"url": _UNRESOLVABLE, "intent": _VALID_INTENT},
                    {"url": "https://example.com/ok", "intent": _BAD_INTENT},
                ]
            },
        )
        assert batch.status_code == 201
        results = batch.json()["results"]
        assert [r["index"] for r in results] == [0, 1, 2]
        assert [r["status"] for r in results] == ["error", "error", "error"]
        assert results[0]["error"]["code"] == "UNSUPPORTED_PROTOCOL"
        assert results[2]["error"]["code"] == "UNSUPPORTED_INTENT"

        # --- Not-found / bad-input matrix ---
        assert authed.get("/api/v1/jobs/does-not-exist").status_code == 404
        assert authed.post("/api/v1/jobs/does-not-exist/cancel").status_code == 404
        assert authed.post("/api/v1/jobs/does-not-exist/retry").status_code == 404
        unknown = authed.get("/api/v1/nope")
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == "NOT_FOUND"
        assert "text/html" not in unknown.headers.get("content-type", "")
        bad_states = authed.get("/api/v1/jobs", params={"states": "BOGUS"})
        assert bad_states.status_code == 422
        bad_cursor = authed.get("/api/v1/jobs", params={"cursor": "!!!"})
        assert bad_cursor.status_code == 422

        # --- Cleanup + SSE wiring over real HTTP ---
        started = time.monotonic()
        cleanup = authed.post("/api/v1/maintenance/cleanup").json()
        print(f"cleanup took {time.monotonic() - started:.1f}s")
        assert set(cleanup) == {
            "urls_redacted",
            "jobs_deleted",
            "directories_deleted",
            "errors",
        }
        with authed.stream("GET", "/api/v1/events") as stream:
            assert stream.status_code == 200
            assert "text/event-stream" in stream.headers.get("content-type", "")

        # --- Oversized body, last: the 413 answer is sent without consuming the
        # request body, so reusing this keep-alive connection afterwards is
        # unreliable (unread bytes look like the next pipelined request). A
        # fresh one-off client keeps the probe hermetic.
        probe = httpx.Client(base_url=base_url, timeout=30.0)
        too_big = probe.post(
            "/api/v1/jobs",
            json={"url": _UNRESOLVABLE, "intent": _VALID_INTENT, "title": "x" * 70000},
            headers={TOKEN_HEADER: token},
        )
        assert too_big.status_code == 413
        probe.close()

        authed.close()
        cookie_client.close()
        anon.close()
    except BaseException:
        print(f"--- server log tail ({log_path}) ---\n{_tail(log_path)}")
        raise
    finally:
        _stop_server(proc)

    # --- Restart on the same data dir: the token and the database survive ---
    port2 = _free_port()
    base_url2 = f"http://127.0.0.1:{port2}"
    proc2 = _start_server(
        port=port2,
        data_dir=data_dir,
        web_dist=web_dist,
        output_root=tmp_path / "downloads",
        log_path=log_path,
    )
    try:
        _wait_for_health(base_url2)
        token2, _ = _fetch_token(base_url2)
        assert token2 == token, "the install token must survive restarts"
        assert (data_dir / "app.db").is_file()
        again = httpx.Client(base_url=base_url2, headers={TOKEN_HEADER: token2}, timeout=30.0)
        assert again.get("/api/v1/jobs").json() == {"jobs": [], "next_cursor": None}
        again.close()
    except BaseException:
        print(f"--- server log tail ({log_path}) ---\n{_tail(log_path)}")
        raise
    finally:
        _stop_server(proc2)

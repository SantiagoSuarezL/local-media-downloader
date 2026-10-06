"""Runtime configuration for the local service.

Defaults are local-first and loopback-only. Every value can be overridden via
environment variables prefixed with ``LMD_`` (e.g. ``LMD_PORT=9000``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765
_DEFAULT_LOG_LEVEL = "INFO"

# Platform-standard directories belong to a later packaging phase; for local
# development the runtime data lives under ./data (which is git-ignored).
_DEFAULT_DATA_DIR = Path("data")

# Built Svelte assets served by FastAPI in production. Derived from this file so
# the packaged app (Phase 16) resolves it from the bundle, and overridable with
# LMD_WEB_DIST. When the directory is absent the API still runs headless (tests,
# dev with the Vite dev server on :5173).
_DEFAULT_WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = _DEFAULT_HOST
    port: int = _DEFAULT_PORT
    log_level: str = _DEFAULT_LOG_LEVEL
    data_dir: Path = field(default_factory=lambda: _DEFAULT_DATA_DIR)
    # Built web UI served from the same loopback origin (Phase 8).
    web_dist: Path = field(default_factory=lambda: _DEFAULT_WEB_DIST)
    # Maximum attempts at automatic recovery are Phase 7; keep the surface small.
    max_health_tool_timeout_seconds: float = 2.0
    # Scheduler budget (Phase 6).
    scheduler_max_active: int = 3
    scheduler_max_downloads: int = 2
    scheduler_max_encoders: int = 1
    scheduler_max_attempts: int = 3
    scheduler_retry_backoff_seconds: float = 2.0
    # Security limits (Phase 10). Small on purpose: the biggest legitimate
    # request is a job payload with a long URL and a nested intent.
    max_request_bytes: int = 64 * 1024
    resolve_rate_limit_per_minute: int = 30

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app.db"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.environ.get("LMD_HOST", _DEFAULT_HOST),
            port=int(os.environ.get("LMD_PORT", str(_DEFAULT_PORT))),
            log_level=os.environ.get("LMD_LOG_LEVEL", _DEFAULT_LOG_LEVEL).upper(),
            data_dir=Path(os.environ.get("LMD_DATA_DIR", str(_DEFAULT_DATA_DIR))),
            web_dist=Path(os.environ.get("LMD_WEB_DIST", str(_DEFAULT_WEB_DIST))),
            max_health_tool_timeout_seconds=float(os.environ.get("LMD_HEALTH_TOOL_TIMEOUT", "2.0")),
            scheduler_max_active=int(os.environ.get("LMD_SCHED_MAX_ACTIVE", "3")),
            scheduler_max_downloads=int(os.environ.get("LMD_SCHED_MAX_DOWNLOADS", "2")),
            scheduler_max_encoders=int(os.environ.get("LMD_SCHED_MAX_ENCODERS", "1")),
            scheduler_max_attempts=int(os.environ.get("LMD_SCHED_MAX_ATTEMPTS", "3")),
            scheduler_retry_backoff_seconds=float(os.environ.get("LMD_SCHED_RETRY_BACKOFF", "2.0")),
            max_request_bytes=int(os.environ.get("LMD_MAX_REQUEST_BYTES", str(64 * 1024))),
            resolve_rate_limit_per_minute=int(os.environ.get("LMD_RESOLVE_RATE_LIMIT", "30")),
        )

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

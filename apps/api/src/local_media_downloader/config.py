"""Runtime configuration for the local service.

Defaults are local-first and loopback-only. Every value can be overridden via
environment variables prefixed with ``LMD_`` (e.g. ``LMD_PORT=9000``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain.output import OutputRule, resolve_output_root
from .services.retention import (
    DEFAULT_HISTORY_RETENTION_DAYS,
    DEFAULT_TEMPORARY_RETENTION_HOURS,
    DEFAULT_URL_RETENTION,
    RetentionPolicy,
)

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

# Final media goes here, never inside the job directory (which holds temporary
# artifacts that retention may delete). Operator-configured, never settable
# from the API.
_DEFAULT_OUTPUT_ROOT = Path.home() / "Downloads" / "Local Media Downloader"


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
    # Output organization (Phase 12). The root is operator configuration; the
    # rule is a closed enum the API may select.
    output_root: Path = field(default_factory=lambda: resolve_output_root(_DEFAULT_OUTPUT_ROOT))
    output_rule: OutputRule = OutputRule.FLAT
    # Retention and cleanup (Phase 12).
    source_url_retention: str = DEFAULT_URL_RETENTION
    history_retention_days: int = DEFAULT_HISTORY_RETENTION_DAYS
    temporary_retention_hours: int = DEFAULT_TEMPORARY_RETENTION_HOURS
    # Reserved for a future phase: the settings key exists so the value can be
    # reported and validated before anything enforces it.
    bandwidth_limit_bps: int | None = None

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def retention_policy(self) -> RetentionPolicy:
        return RetentionPolicy(
            source_url_retention=self.source_url_retention,
            history_retention_days=self.history_retention_days,
            temporary_retention_hours=self.temporary_retention_hours,
        )

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
            output_root=resolve_output_root(
                os.environ.get("LMD_OUTPUT_ROOT", str(_DEFAULT_OUTPUT_ROOT))
            ),
            output_rule=OutputRule(os.environ.get("LMD_OUTPUT_RULE", OutputRule.FLAT.value)),
            source_url_retention=os.environ.get("LMD_SOURCE_URL_RETENTION", DEFAULT_URL_RETENTION),
            history_retention_days=int(
                os.environ.get("LMD_HISTORY_RETENTION_DAYS", str(DEFAULT_HISTORY_RETENTION_DAYS))
            ),
            temporary_retention_hours=int(
                os.environ.get(
                    "LMD_TEMPORARY_RETENTION_HOURS", str(DEFAULT_TEMPORARY_RETENTION_HOURS)
                )
            ),
            bandwidth_limit_bps=(
                int(os.environ["LMD_BANDWIDTH_LIMIT_BPS"])
                if os.environ.get("LMD_BANDWIDTH_LIMIT_BPS")
                else None
            ),
        )

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

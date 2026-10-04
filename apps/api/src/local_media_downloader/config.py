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


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = _DEFAULT_HOST
    port: int = _DEFAULT_PORT
    log_level: str = _DEFAULT_LOG_LEVEL
    data_dir: Path = field(default_factory=lambda: _DEFAULT_DATA_DIR)
    # Maximum attempts at automatic recovery are Phase 7; keep the surface small.
    max_health_tool_timeout_seconds: float = 2.0

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
            max_health_tool_timeout_seconds=float(os.environ.get("LMD_HEALTH_TOOL_TIMEOUT", "2.0")),
        )

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

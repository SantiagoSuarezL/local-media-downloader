"""Environment diagnostics reported by /api/v1/health.

All tool probes run through explicit argv (no shell, no interpolation) and a
short timeout. Detection only reports presence/version; it never executes an
extraction against a URL, so it is safe to call on every health check.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

_EXE_YT_DLP = "yt-dlp"
_EXE_DENO = "deno"
_EXE_FFMPEG = "ffmpeg"
_EXE_FFPROBE = "ffprobe"


@dataclass(frozen=True, slots=True)
class ToolStatus:
    name: str
    detected: bool
    version: str | None

    def as_dict(self) -> dict[str, object]:
        return {"detected": self.detected, "version": self.version}


def _probe(exe: str, args: list[str], timeout: float) -> str | None:
    try:
        completed = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[0].strip() if output else None


def detect_tools(timeout: float = 2.0) -> dict[str, ToolStatus]:
    yt_dlp = _probe(_EXE_YT_DLP, ["--version"], timeout)
    # yt-dlp-ejs ships as a Python package for the bundled runtime; probe both the
    # import and the executable that yt-dlp may shell out to.
    yt_dlp_ejs: str | None = None
    try:
        from yt_dlp_ejs import __version__ as ejs_version  # type: ignore[import-not-found]

        yt_dlp_ejs = str(ejs_version)
    except ImportError:
        pass
    deno = _probe(_EXE_DENO, ["--version"], timeout)
    ffmpeg = _probe(_EXE_FFMPEG, ["-version"], timeout)
    ffprobe = _probe(_EXE_FFPROBE, ["-version"], timeout)

    def status(name: str, version: str | None) -> ToolStatus:
        return ToolStatus(name=name, detected=version is not None, version=version)

    return {
        "yt_dlp": status("yt-dlp", yt_dlp),
        "yt_dlp_ejs": status("yt-dlp-ejs", yt_dlp_ejs),
        "deno": status("Deno", deno),
        "ffmpeg": status("FFmpeg", ffmpeg),
        "ffprobe": status("FFprobe", ffprobe),
    }


def database_ready(database_path: Path, timeout: float = 2.0) -> tuple[bool, str]:
    """Return (ok, detail). No schema exists in Phase 1; this validates that the
    sqlite3 driver works and the target directory is writable for when the schema
    lands in Phase 2. Nothing is persisted — the probe file is a temporary
    in-memory database."""
    try:
        with sqlite3.connect(":memory:") as conn:
            conn.execute("SELECT 1")
    except sqlite3.Error as exc:  # pragma: no cover - environment anomaly
        return False, f"sqlite3 unavailable: {exc}"
    parent = database_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return False, f"storage dir not writable: {exc}"
    return True, "ok"


def storage_ready(data_dir: Path) -> tuple[bool, str]:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"cannot create data dir: {exc}"
    probe = data_dir / ".write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return False, f"data dir not writable: {exc}"
    try:
        free = shutil.disk_usage(data_dir).free
    except OSError:
        return True, "ok"
    return True, f"ok ({free // (1024**3)} GiB free)"

"""Environment diagnostics reported by /api/v1/health.

All tool probes run through explicit argv (no shell, no interpolation) and a
short timeout. Detection only reports presence/version; it never executes an
extraction against a URL, so it is safe to call on every health check.
"""

from __future__ import annotations

import shutil
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

"""Environment diagnostics reported by /api/v1/health.

All tool probes run through explicit argv (no shell, no interpolation) and a
short timeout. Detection only reports presence/version; it never executes an
extraction against a URL, so it is safe to call on every health check.

Every probe resolves its tool through :mod:`.tool_paths`, the same resolution the
adapters use, so the report describes the binaries that will really run. Probing
``PATH`` directly used to report ``deno: no`` while the extractor was happily
running the workspace Deno from ``node_modules/.bin`` -- a diagnostic that
contradicts itself is worse than none. Only the version line is reported: no
resolved path may leak into the payload (health is reachable without a token).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .adapters.tool_paths import ffmpeg_argv, ffprobe_argv, find_deno, yt_dlp_argv


@dataclass(frozen=True, slots=True)
class ToolStatus:
    name: str
    detected: bool
    version: str | None

    def as_dict(self) -> dict[str, object]:
        return {"detected": self.detected, "version": self.version}


def _probe(argv: list[str], timeout: float) -> str | None:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[0].strip() if output else None


def _ejs_version() -> str | None:
    """Version of the optional yt-dlp-ejs challenge solvers.

    The package exposes ``version`` (0.8.x) and no ``__version__``, so both
    spellings are accepted: reading only ``__version__`` reported
    ``yt-dlp-ejs: no`` on an environment where the solvers were installed and
    Deno was right there.
    """
    try:
        import yt_dlp_ejs  # type: ignore[import-not-found]
    except ImportError:
        return None
    version = getattr(yt_dlp_ejs, "version", None) or getattr(yt_dlp_ejs, "__version__", None)
    return str(version) if version else "unknown"


def detect_tools(timeout: float = 2.0) -> dict[str, ToolStatus]:
    # yt-dlp is always the pinned module of this environment, never a PATH shim:
    # the report has to describe the binary the adapter will really spawn.
    yt_dlp = _probe([*yt_dlp_argv(), "--version"], timeout)
    # yt-dlp-ejs ships as a Python package for the bundled runtime; its presence
    # is what lets yt-dlp solve the JS challenges of some sites.
    yt_dlp_ejs = _ejs_version()
    deno_path = find_deno()
    deno = _probe([deno_path, "--version"], timeout) if deno_path is not None else None
    ffmpeg = _probe([*ffmpeg_argv(), "-version"], timeout)
    ffprobe = _probe([*ffprobe_argv(), "-version"], timeout)

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

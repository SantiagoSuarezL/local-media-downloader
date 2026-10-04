"""Executable resolution for external tools.

The application must not depend on the user's global PATH
(TECHNICAL_SPEC §26), so tools are looked up in a fixed order:

1. an explicit override (settings / future bundled ``data/bin``);
2. the workspace's ``node_modules/.bin`` — this is how the pnpm-managed Deno
   runtime is found in development;
3. the uv-managed virtual environment that runs this process;
4. ``PATH`` as a last resort.

yt-dlp is never resolved from PATH at all: it is a versioned dependency of the
uv environment and is always invoked as ``sys.executable -m yt_dlp``, so the
exact version pinned in ``uv.lock`` is the one that runs.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_WORKSPACE_ROOT = _PACKAGE_ROOT.parents[1]
_DENO_EXECUTABLES = ("deno", "deno.exe")


def node_bin_candidates() -> list[Path]:
    """Directories that may hold pnpm-managed executables, most specific first.

    The first entry is derived from this file's location, which is correct for
    an editable install. The CWD fallback covers a non-editable install or a
    service started from another directory.
    """
    candidates = [_WORKSPACE_ROOT / "node_modules" / ".bin"]
    cwd_bin = Path.cwd() / "node_modules" / ".bin"
    if cwd_bin not in candidates:
        candidates.append(cwd_bin)
    return candidates


def workspace_node_bin() -> Path:
    return _WORKSPACE_ROOT / "node_modules" / ".bin"


def find_deno(explicit: str | None = None) -> str | None:
    """Locate the Deno executable, or ``None`` when it is not installed."""
    if explicit:
        return explicit if Path(explicit).exists() else None
    for directory in node_bin_candidates():
        for name in _DENO_EXECUTABLES:
            candidate = directory / name
            if candidate.exists():
                return str(candidate)
    return shutil.which("deno")


def yt_dlp_argv() -> list[str]:
    """Argv prefix that runs the pinned yt-dlp from this environment."""
    return [sys.executable, "-m", "yt_dlp"]


def python_environment_bin() -> Path | None:
    """The ``Scripts``/``bin`` directory of the active uv environment."""
    prefix = Path(sys.prefix)
    for name in ("Scripts", "bin"):
        candidate = prefix / name
        if candidate.exists():
            return candidate
    return None


def ffmpeg_argv() -> list[str]:
    """Resolve FFmpeg preferring the environment over PATH."""
    override = os.environ.get("LMD_FFMPEG")
    if override:
        return [override]
    env_bin = python_environment_bin()
    if env_bin is not None:
        for name in ("ffmpeg", "ffmpeg.exe"):
            candidate = env_bin / name
            if candidate.exists():
                return [str(candidate)]
    found = shutil.which("ffmpeg")
    return [found] if found else ["ffmpeg"]

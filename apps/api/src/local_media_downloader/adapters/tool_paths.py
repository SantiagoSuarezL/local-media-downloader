"""Executable resolution for external tools.

The application must not depend on the user's global PATH
(TECHNICAL_SPEC §26), so tools are looked up in a fixed order:

1. an explicit override (settings / future bundled ``data/bin``);
2. bundled binaries next to the executable (PyInstaller onedir, Phase 16);
3. the workspace's ``node_modules/.bin`` — this is how the pnpm-managed Deno
   runtime is found in development;
4. the uv-managed virtual environment that runs this process;
5. ``PATH`` as a last resort.

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


def _bundle_bin_candidates() -> list[Path]:
    """Bundle ``bin/`` next to the running executable (PyInstaller onedir).

    Computed at call time, not at import, so tests can stage a fake bundle and
    frozen processes always see their own directory. In development the
    interpreter lives in the uv venv, whose parent directory holds no ``bin/``
    with tools, so this is empty and resolution falls through to
    node_modules/venv/PATH unchanged.
    """
    bundle_bin = Path(sys.executable).resolve().parent / "bin"
    return [bundle_bin] if bundle_bin.is_dir() else []


def find_deno(explicit: str | None = None) -> str | None:
    """Locate the Deno executable, or ``None`` when it is not installed."""
    if explicit:
        return explicit if Path(explicit).exists() else None
    # 2) bundled
    for directory in _bundle_bin_candidates():
        for name in _DENO_EXECUTABLES:
            candidate = directory / name
            if candidate.exists():
                return str(candidate)
    # 3) workspace node_modules
    for directory in node_bin_candidates():
        for name in _DENO_EXECUTABLES:
            candidate = directory / name
            if candidate.exists():
                return str(candidate)
    # 4) fallback to PATH
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


def _tool_argv(env_var: str, names: tuple[str, ...]) -> list[str]:
    override = os.environ.get(env_var)
    if override:
        return [override]
    # 2) bundled binaries
    for directory in _bundle_bin_candidates():
        for name in names:
            candidate = directory / name
            if candidate.exists():
                return [str(candidate)]
    # 3) uv venv
    env_bin = python_environment_bin()
    if env_bin is not None:
        for name in names:
            candidate = env_bin / name
            if candidate.exists():
                return [str(candidate)]
    found = shutil.which(names[0])
    return [found] if found else [names[0]]


def ffmpeg_argv() -> list[str]:
    """Resolve FFmpeg preferring the environment over PATH."""
    return _tool_argv("LMD_FFMPEG", ("ffmpeg", "ffmpeg.exe"))


def ffprobe_argv() -> list[str]:
    """Resolve FFprobe preferring the environment over PATH."""
    return _tool_argv("LMD_FFPROBE", ("ffprobe", "ffprobe.exe"))

"""Output filename policy.

The final filename comes from data the user (or the remote site) controls:
``jobs.title`` arrives from yt-dlp metadata. Feeding that straight into a path
would let a title such as ``../../evil`` or ``C:\\Windows\\System32\\x`` decide
where a file lands, so every final name is sanitized here and then proven to be
inside its job's output directory.

Rules are deliberately cross-platform: the app may run on Windows (Phase 16
ships Windows first), so names are built for the strictest target.
"""

from __future__ import annotations

import re
from pathlib import Path

# Characters Windows forbids in a filename, plus path separators.
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")

# Windows keeps the names of these devices no matter the extension.
_RESERVED = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

MAX_STEM_LENGTH = 120


def sanitize_filename(name: str | None, *, fallback: str = "download", extension: str = "") -> str:
    """Return a safe single path segment with ``extension`` appended.

    Never raises: a hostile title degrades to ``fallback`` instead of failing
    the job after the media was already downloaded.
    """
    stem = _FORBIDDEN.sub(" ", name or "")
    stem = _WHITESPACE.sub(" ", stem).strip(" .")
    # A name made only of dots/dots-and-spaces is never usable.
    if not stem or set(stem) <= {".", " "}:
        stem = fallback
    if stem.lower() in _RESERVED:
        stem = f"{stem}-file"
    if len(stem) > MAX_STEM_LENGTH:
        stem = stem[:MAX_STEM_LENGTH].rstrip(" .")
    suffix = extension.strip().lstrip(".")
    suffix = _FORBIDDEN.sub("", suffix)
    return f"{stem}.{suffix}" if suffix else stem


def output_path_for(base_dir: Path, name: str | None, *, fallback: str, extension: str) -> Path:
    """Build the final output path and prove it stays inside ``base_dir``.

    ``sanitize_filename`` already removes separators; the containment check is
    deliberate defense in depth so a future change to the sanitizer can never
    silently turn into a write outside the job directory.
    """
    filename = sanitize_filename(name, fallback=fallback, extension=extension)
    base = base_dir.resolve()
    candidate = (base / filename).resolve()
    if candidate.parent != base:
        raise ValueError(f"refusing to write outside {base}: {candidate}")
    return candidate

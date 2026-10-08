"""FFprobe adapter.

Owns every interaction with ffprobe. The rest of the application sees only the
``MetadataInspector`` port and normalized models.

Invariants enforced here:
- arguments are always passed as an argv list, never a shell string
  (ENGINEERING_PRINCIPLES #8);
- the CLI surface is never exposed upward (TECHNICAL_SPEC §1);
- exit code 0 is never trusted as "valid output" — stdout is parsed and the
  result is validated (ENGINEERING_PRINCIPLES #7);
- no contact with the network: a local file is the only accepted input.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ..domain.errors import ErrorCode, ExtractionError
from ..domain.probe import MediaProbe, StreamKind, StreamProbe
from ..logging_config import get_logger
from .tool_paths import ffprobe_argv

_LOGGER = get_logger("inspector.ffprobe")

DEFAULT_TIMEOUT = 30.0


class FFprobeInspector:
    """``MetadataInspector`` implementation backed by ffprobe."""

    @property
    def name(self) -> str:
        return "ffprobe"

    @property
    def version(self) -> str | None:
        try:
            completed = subprocess.run(
                [*ffprobe_argv(), "-version"],
                capture_output=True,
                text=True,
                timeout=10.0,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None
        if completed.returncode != 0:
            return None
        first = (completed.stdout or completed.stderr).strip().splitlines()
        return first[0] if first else None

    def inspect(self, path: Path, *, timeout: float = DEFAULT_TIMEOUT) -> MediaProbe:
        if not path.exists():
            raise ExtractionError(
                ErrorCode.SOURCE_UNAVAILABLE,
                "The media file does not exist.",
                detail=str(path),
                retryable=False,
            )
        argv = [
            *ffprobe_argv(),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        _LOGGER.debug("ffprobe_start", extra={"argv_len": len(argv)})
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExtractionError(
                ErrorCode.TIMEOUT,
                "Probing the file took too long.",
                detail=str(exc),
                retryable=True,
            ) from exc
        except FileNotFoundError as exc:
            raise ExtractionError(
                ErrorCode.TOOL_MISSING,
                "ffprobe is not available.",
                detail=str(exc),
                retryable=False,
            ) from exc
        if completed.returncode != 0:
            raise ExtractionError(
                ErrorCode.EXTRACTION_FAILED,
                "ffprobe could not read the file.",
                detail=completed.stderr.strip() or f"exit {completed.returncode}",
                retryable=False,
            )
        return parse_probe(completed.stdout, path=path)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_fps(stream: dict[str, Any]) -> float | None:
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = stream.get(key)
        if isinstance(raw, str) and "/" in raw:
            num, _, den = raw.partition("/")
            try:
                numerator = float(num)
                denominator = float(den)
            except ValueError:
                continue
            if denominator > 0 and numerator > 0:
                return numerator / denominator
    return None


def _parse_stream(raw: dict[str, Any]) -> StreamProbe:
    codec_type = raw.get("codec_type")
    kind = {
        "video": StreamKind.VIDEO,
        "audio": StreamKind.AUDIO,
        "subtitle": StreamKind.SUBTITLE,
    }.get(str(codec_type), StreamKind.OTHER)
    try:
        index = int(raw.get("index", 0))
    except (TypeError, ValueError):
        index = 0
    # Older ffprobe builds report width/height 0 for animated WebP while the
    # coded dimensions are correct; prefer container dims, fall back to coded.
    # (0 is never a real dimension, so `or` is safe here.)
    width = _as_int(raw.get("width")) or _as_int(raw.get("coded_width"))
    height = _as_int(raw.get("height")) or _as_int(raw.get("coded_height"))
    return StreamProbe(
        index=index,
        kind=kind,
        codec_name=raw.get("codec_name") if isinstance(raw.get("codec_name"), str) else None,
        width=width,
        height=height,
        fps=_parse_fps(raw) if kind is StreamKind.VIDEO else None,
        sample_rate=_as_int(raw.get("sample_rate")),
        channels=_as_int(raw.get("channels")),
        bitrate=_as_int(raw.get("bit_rate")),
    )


def parse_probe(stdout: str, *, path: Path) -> MediaProbe:
    """Translate ffprobe JSON stdout into a :class:`MediaProbe`."""
    text = stdout.strip()
    if not text:
        raise ExtractionError(
            ErrorCode.EXTRACTION_FAILED,
            "ffprobe returned no data.",
            detail=f"empty stdout for {path}",
            retryable=False,
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(
            ErrorCode.EXTRACTION_FAILED,
            "ffprobe returned malformed data.",
            detail=str(exc),
            retryable=False,
        ) from exc
    if not isinstance(payload, dict):
        raise ExtractionError(
            ErrorCode.EXTRACTION_FAILED,
            "ffprobe returned an unexpected response.",
            detail=type(payload).__name__,
            retryable=False,
        )
    fmt = payload.get("format")
    if not isinstance(fmt, dict):
        raise ExtractionError(
            ErrorCode.EXTRACTION_FAILED,
            "ffprobe returned no container information.",
            detail=f"no format block for {path}",
            retryable=False,
        )
    raw_streams = payload.get("streams")
    streams = (
        tuple(_parse_stream(s) for s in raw_streams if isinstance(s, dict))
        if isinstance(raw_streams, list)
        else ()
    )
    return MediaProbe(
        path=str(path),
        container=fmt.get("format_name") if isinstance(fmt.get("format_name"), str) else None,
        duration_seconds=_as_float(fmt.get("duration")),
        size_bytes=_as_int(fmt.get("size")),
        bitrate=_as_int(fmt.get("bit_rate")),
        streams=streams,
    )

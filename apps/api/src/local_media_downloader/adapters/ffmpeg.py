"""FFmpeg adapter.

Owns every interaction with ffmpeg. The rest of the application sees only the
``MediaProcessor`` port and normalized models.

Invariants enforced here:
- arguments are always passed as an argv list, never a shell string
  (ENGINEERING_PRINCIPLES #8);
- a produced file is never trusted without post-validation: every operation
  re-inspects the output with ``FFprobeInspector`` (ENGINEERING_PRINCIPLES #7,
  #17);
- stream copy is preferred; transcoding happens only when the intent cannot
  be satisfied by remuxing (ENGINEERING_PRINCIPLES #84);
- the CLI surface is never exposed upward (TECHNICAL_SPEC §1).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..domain.errors import ErrorCode, ExtractionError
from ..domain.probe import MediaProbe
from ..logging_config import get_logger
from .ffprobe import FFprobeInspector
from .tool_paths import ffmpeg_argv

_LOGGER = get_logger("processor.ffmpeg")

DEFAULT_TIMEOUT = 600.0


class FFmpegProcessor:
    """``MediaProcessor`` implementation backed by ffmpeg."""

    def __init__(self, *, inspector: FFprobeInspector | None = None) -> None:
        self._inspector = inspector or FFprobeInspector()

    @property
    def name(self) -> str:
        return "ffmpeg"

    @property
    def version(self) -> str | None:
        try:
            completed = subprocess.run(
                [*ffmpeg_argv(), "-version"],
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

    def remux(self, source: Path, destination: Path, *, timeout: float = DEFAULT_TIMEOUT) -> Path:
        """Copy all streams into a new container without re-encoding."""
        return self._run(source, destination, ["-c", "copy", "-map", "0"], timeout=timeout)

    def transcode(
        self,
        source: Path,
        destination: Path,
        *,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Path:
        """Re-encode video and audio into a self-contained file."""
        return self._run(
            source,
            destination,
            ["-c:v", video_codec, "-preset", "veryfast", "-c:a", audio_codec],
            timeout=timeout,
        )

    def extract_audio(
        self,
        source: Path,
        destination: Path,
        *,
        codec: str = "libmp3lame",
        bitrate: str = "192k",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Path:
        """Extract the audio track only."""
        return self._run(
            source,
            destination,
            ["-vn", "-c:a", codec, "-b:a", bitrate],
            timeout=timeout,
        )

    def video_only(
        self, source: Path, destination: Path, *, timeout: float = DEFAULT_TIMEOUT
    ) -> Path:
        """Keep only the video stream, dropping audio (and subtitles)."""
        return self._run(
            source,
            destination,
            ["-map", "0:v:0", "-c:v", "copy", "-an"],
            timeout=timeout,
        )

    def validate(self, path: Path, *, timeout: float = 30.0) -> MediaProbe:
        """Re-inspect a produced file and assert it is a plausible media file."""
        if not path.exists():
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                "The produced file does not exist.",
                detail=str(path),
                retryable=False,
            )
        if path.stat().st_size == 0:
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                "The produced file is empty.",
                detail=str(path),
                retryable=False,
            )
        probe = self._inspector.inspect(path, timeout=timeout)
        if not probe.streams:
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                "The produced file has no streams.",
                detail=str(path),
                retryable=False,
            )
        if probe.duration_seconds is not None and probe.duration_seconds <= 0:
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                "The produced file reports a non-positive duration.",
                detail=str(probe.duration_seconds),
                retryable=False,
            )
        return probe

    def _run(
        self,
        source: Path,
        destination: Path,
        operation_args: list[str],
        *,
        timeout: float,
    ) -> Path:
        if not source.exists():
            raise ExtractionError(
                ErrorCode.SOURCE_UNAVAILABLE,
                "The source file does not exist.",
                detail=str(source),
                retryable=False,
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            *ffmpeg_argv(),
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            *operation_args,
            str(destination),
        ]
        _LOGGER.debug("ffmpeg_start", extra={"argv_len": len(argv)})
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
            destination.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.TIMEOUT,
                "Processing the file took too long.",
                detail=str(exc),
                retryable=True,
            ) from exc
        except FileNotFoundError as exc:
            raise ExtractionError(
                ErrorCode.TOOL_MISSING,
                "ffmpeg is not available.",
                detail=str(exc),
                retryable=False,
            ) from exc
        if completed.returncode != 0:
            destination.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.EXTRACTION_FAILED,
                "ffmpeg could not process the file.",
                detail=completed.stderr.strip() or f"exit {completed.returncode}",
                retryable=False,
            )
        self.validate(destination, timeout=30.0)
        return destination

"""yt-dlp adapter.

Owns every interaction with yt-dlp. The rest of the application sees only the
``Extractor`` port and normalized models.

Invariants enforced here:
- arguments are always passed as an argv list, never a shell string
  (ENGINEERING_PRINCIPLES #8);
- the pinned yt-dlp from this uv environment is used, never a PATH copy;
- the CLI surface is never exposed upward (TECHNICAL_SPEC §1);
- exit code 0 is never trusted as "valid output" — stdout is parsed and the
  result is validated (ENGINEERING_PRINCIPLES #7).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..domain.errors import ErrorCode, ExtractionError
from ..domain.media import MediaInfo
from ..domain.urls import validate_url
from ..logging_config import get_logger
from . import errors as error_mapping
from .normalize import normalize
from .progress import TEMPLATE, DownloadProgress, parse_progress_line
from .tool_paths import find_deno, yt_dlp_argv

_LOGGER = get_logger("extractor.ytdlp")

# Enough for metadata resolution without letting a hostile site stall the API.
DEFAULT_TIMEOUT = 30.0


class YtDlpExtractor:
    """``Extractor`` implementation backed by yt-dlp."""

    def __init__(
        self,
        *,
        deno_path: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._deno_path = deno_path
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "yt-dlp"

    @property
    def version(self) -> str | None:
        """Installed yt-dlp version, or ``None`` when it cannot be determined."""
        completed = self._run(["--version"], timeout=10.0)
        if completed.returncode != 0:
            return None
        return completed.stdout.strip() or None

    def base_argv(self) -> list[str]:
        argv = yt_dlp_argv()
        deno = self._deno_path or find_deno()
        if deno:
            # yt-dlp needs a JS runtime for the yt-dlp-ejs challenge solvers.
            argv += ["--js-runtimes", f"deno:{deno}"]
        return argv

    def _run(
        self,
        args: list[str],
        *,
        timeout: float | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        argv = [*self.base_argv(), *args]
        _LOGGER.debug("ytdlp_start", extra={"argv_len": len(argv)})
        try:
            return subprocess.run(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout if timeout is not None else self._timeout,
                check=False,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExtractionError(
                ErrorCode.TIMEOUT,
                "The source took too long to respond.",
                detail=str(exc),
                retryable=True,
            ) from exc
        except FileNotFoundError as exc:
            raise ExtractionError(
                ErrorCode.TOOL_MISSING,
                "The extraction tool is not available.",
                detail=str(exc),
                retryable=False,
            ) from exc

    def resolve(self, url: str, *, timeout: float | None = None) -> MediaInfo:
        """Resolve metadata for a URL into normalized ``MediaInfo``."""
        validated = validate_url(url)
        completed = self._run(
            [
                "--dump-single-json",
                "--no-playlist",
                "--no-warnings",
                "--no-progress",
                "--skip-download",
                "--socket-timeout",
                "20",
                validated,
            ],
            timeout=timeout,
        )
        if completed.returncode != 0:
            raise error_mapping.classify(completed.stderr, exit_code=completed.returncode)

        payload = self._parse_json(completed.stdout, url=validated)
        if not isinstance(payload, dict):
            raise ExtractionError(
                ErrorCode.EXTRACTION_FAILED,
                "The extractor returned an unexpected response.",
                detail=type(payload).__name__,
                retryable=False,
            )
        return normalize(payload, requested_url=validated)

    @staticmethod
    def _parse_json(stdout: str, *, url: str) -> Any:
        text = stdout.strip()
        if not text:
            raise ExtractionError(
                ErrorCode.EXTRACTION_FAILED,
                "The extractor returned no data.",
                detail=f"empty stdout for {url}",
                retryable=False,
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExtractionError(
                ErrorCode.EXTRACTION_FAILED,
                "The extractor returned malformed data.",
                detail=str(exc),
                retryable=False,
            ) from exc

    def download(
        self,
        url: str,
        *,
        destination: Path,
        format_selector: str,
        timeout: float | None = None,
    ) -> Iterator[DownloadProgress]:
        """Stream structured download progress.

        Progress is produced by yt-dlp's own ``--progress-template``; the human
        readable line is never parsed.
        """
        validated = validate_url(url)
        destination.mkdir(parents=True, exist_ok=True)
        argv = [
            *self.base_argv(),
            "--newline",
            "--progress-template",
            TEMPLATE,
            "--no-part",
            "--no-playlist",
            "--format",
            format_selector,
            "--output",
            str(destination / "%(id)s.%(ext)s"),
            validated,
        ]
        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise ExtractionError(
                ErrorCode.TOOL_MISSING,
                "The extraction tool is not available.",
                detail=str(exc),
                retryable=False,
            ) from exc

        assert process.stdout is not None
        try:
            for line in process.stdout:
                progress = parse_progress_line(line)
                if progress is not None:
                    yield progress
        finally:
            process.stdout.close()
            stderr = process.stderr.read() if process.stderr else ""
            if process.stderr:
                process.stderr.close()
            returncode = process.wait()
            if returncode != 0:
                raise error_mapping.classify(stderr, exit_code=returncode)

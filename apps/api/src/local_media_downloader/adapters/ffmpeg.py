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

import re
import subprocess
from dataclasses import replace
from pathlib import Path

from ..domain.errors import ErrorCode, ExtractionError
from ..domain.probe import MediaProbe, StreamKind
from ..logging_config import get_logger
from .ffprobe import FFprobeInspector
from .tool_paths import ffmpeg_argv

_LOGGER = get_logger("processor.ffmpeg")

# First `s:WxH` of a showinfo line: decoded-frame dimensions, e.g.
# `[Parsed_showinfo_0 ...] n: 0 ... s:512x512 ...` (spacing after `s:`
# varies by build, hence `\s*`).
_DECODED_DIMS = re.compile(r"s:\s*(\d+)x(\d+)")

DEFAULT_TIMEOUT = 600.0

LOUNDNORM_FILTER = "loudnorm=I=-14:LRA=11:TP=-1.5"


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
        video_bitrate: str | None = None,
        video_framerate: str | None = None,
        audio_normalize: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Path:
        """Re-encode video and audio into a self-contained file."""
        audio_filters = [LOUNDNORM_FILTER] if audio_normalize and audio_codec != "none" else []
        return self._run(
            source,
            destination,
            [
                *(["-vf", f"fps={video_framerate}"] if video_framerate is not None else []),
                "-c:v",
                video_codec,
                *_cpu_args(video_codec),
                *(["-b:v", video_bitrate] if video_bitrate is not None else []),
                *(["-af", ",".join(audio_filters)] if audio_filters else []),
                *(["-an"] if audio_codec == "none" else ["-c:a", audio_codec]),
            ],
            timeout=timeout,
        )

    def transcode_trimmed(
        self,
        source: Path,
        destination: Path,
        *,
        start: float,
        end: float,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        resize_target: str | None = None,
        crop_box: str | None = None,
        video_bitrate: str | None = None,
        video_framerate: str | None = None,
        audio_normalize: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Path:
        """Re-encode only the ``[start, end)`` window (accurate cut, never stream copy).

        When ``resize_target`` (``720p`` or ``1280x720`` bbox) and/or ``crop_box``
        (``640x480`` or ``640x480+100+50``) are given, the geometry filters are
        applied in the same pass — trim + crop + resize never run as two lossy
        encodes. Crop is applied BEFORE scale: the box is expressed in source
        coordinates, so it must select the pixels before they are scaled.
        """
        result = self._run(
            source,
            destination,
            [
                *_trim_args(start, end),
                *_video_filter_args(resize_target, crop_box, video_framerate),
                "-c:v",
                video_codec,
                *_cpu_args(video_codec),
                *(["-b:v", video_bitrate] if video_bitrate is not None else []),
                *(["-af", LOUNDNORM_FILTER] if audio_normalize and audio_codec != "none" else []),
                *(["-an"] if audio_codec == "none" else ["-c:a", audio_codec]),
            ],
            timeout=timeout,
        )
        checked = self._check_trimmed(result, start, end)
        if crop_box is not None and resize_target is None:
            # Exact-box check only holds when no scale follows: a single pass
            # produces a single file, so after crop+scale the dimensions are
            # the scaled ones (validated below by _check_resized).
            checked = self._check_cropped(checked, crop_box)
        if resize_target is not None:
            return self._check_resized(checked, resize_target)
        return checked

    def extract_audio_trimmed(
        self,
        source: Path,
        destination: Path,
        *,
        start: float,
        end: float,
        codec: str = "libmp3lame",
        bitrate: str = "192k",
        audio_normalize: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Path:
        """Extract the ``[start, end)`` window of the audio track."""
        result = self._run(
            source,
            destination,
            [
                *_trim_args(start, end),
                "-vn",
                "-c:a",
                codec,
                "-b:a",
                bitrate,
                *(["-af", LOUNDNORM_FILTER] if audio_normalize else []),
            ],
            timeout=timeout,
        )
        return self._check_trimmed(result, start, end)

    def _check_trimmed(self, result: Path, start: float, end: float) -> Path:
        try:
            probe = self.validate(result)
        except ExtractionError:
            result.unlink(missing_ok=True)
            raise
        duration = probe.duration_seconds
        if duration is not None and duration > (end - start) + 1.0:
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                "Trimmed output is longer than the requested range.",
                retryable=False,
            )
        return result

    def extract_audio(
        self,
        source: Path,
        destination: Path,
        *,
        codec: str = "libmp3lame",
        bitrate: str = "192k",
        audio_normalize: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Path:
        """Extract the audio track only."""
        return self._run(
            source,
            destination,
            [
                "-vn",
                "-c:a",
                codec,
                "-b:a",
                bitrate,
                *(["-af", LOUNDNORM_FILTER] if audio_normalize else []),
            ],
            timeout=timeout,
        )

    def resize(
        self,
        source: Path,
        destination: Path,
        *,
        target: str,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        video_bitrate: str | None = None,
        video_framerate: str | None = None,
        audio_normalize: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Path:
        """Resize video to target height (``720p``) or bbox (``1280x720``).

        ``1280x720`` is a maximum bounding box preserving aspect ratio
        (4:3 → 960x720), never an exact deforming stretch. Always transcodes —
        stream copy cannot change resolution.
        """
        result = self._run(
            source,
            destination,
            [
                "-vf",
                _scale_filter(target)
                + (f",fps={video_framerate}" if video_framerate is not None else ""),
                "-c:v",
                video_codec,
                *_cpu_args(video_codec),
                *(["-b:v", video_bitrate] if video_bitrate is not None else []),
                *(["-af", LOUNDNORM_FILTER] if audio_normalize and audio_codec != "none" else []),
                *(["-an"] if audio_codec == "none" else ["-c:a", audio_codec]),
            ],
            timeout=timeout,
        )
        return self._check_resized(result, target)

    def crop(
        self,
        source: Path,
        destination: Path,
        *,
        box: str,
        resize_target: str | None = None,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        video_bitrate: str | None = None,
        video_framerate: str | None = None,
        audio_normalize: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Path:
        """Cut out the exact rectangle ``box`` (``640x480`` / ``640x480+100+50``).

        Unlike :meth:`resize`, the output geometry is EXACTLY the requested box:
        cropping discards pixels, it never rescales them. When ``resize_target``
        is also given, the scale runs in the same pass after the crop, so a
        cropped-then-scaled job is encoded once.
        Always transcodes — stream copy cannot change the visible frame.
        """
        result = self._run(
            source,
            destination,
            [
                *_video_filter_args(resize_target, box, video_framerate),
                "-c:v",
                video_codec,
                *_cpu_args(video_codec),
                *(["-b:v", video_bitrate] if video_bitrate is not None else []),
                *(["-af", LOUNDNORM_FILTER] if audio_normalize and audio_codec != "none" else []),
                *(["-an"] if audio_codec == "none" else ["-c:a", audio_codec]),
            ],
            timeout=timeout,
        )
        if resize_target is not None:
            # Same single-pass reason as in transcode_trimmed: the final file
            # holds scaled dimensions, so only the bbox check applies.
            return self._check_resized(result, resize_target)
        return self._check_cropped(result, box)

    def _check_cropped(self, result: Path, box: str) -> Path:
        try:
            probe = self.validate(result)
        except ExtractionError:
            result.unlink(missing_ok=True)
            raise
        video = probe.video_stream
        if video is None or video.width is None or video.height is None:
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                "Cropped output has unknown dimensions.",
                retryable=False,
            )
        expected_w, expected_h = _crop_size(box)
        if (video.width, video.height) != (expected_w, expected_h):
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                f"Cropped {video.width}x{video.height} does not match box {box}.",
                retryable=False,
            )
        return result

    def _check_resized(self, result: Path, target: str) -> Path:
        try:
            probe = self.validate(result)
        except ExtractionError:
            result.unlink(missing_ok=True)
            raise
        video = probe.video_stream
        if video is None:
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                "Resized output has no video stream.",
                retryable=False,
            )
        if target.endswith("p"):
            expected_height = int(target[:-1])
            if video.height is not None and video.height != expected_height:
                result.unlink(missing_ok=True)
                raise ExtractionError(
                    ErrorCode.VALIDATION_FAILED,
                    f"Resized height {video.height} != target {expected_height}.",
                    retryable=False,
                )
            return result
        try:
            target_w, target_h = (int(part) for part in target.lower().split("x"))
        except ValueError:
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                f"Invalid resize target {target!r}.",
                retryable=False,
            ) from None
        width, height = video.width, video.height
        if width is None or height is None:
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                "Resized output has unknown dimensions.",
                retryable=False,
            )
        fits = width <= target_w + 2 and height <= target_h + 2
        touches = abs(width - target_w) <= 2 or abs(height - target_h) <= 2
        if not (fits and touches):
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED,
                f"Resized {width}x{height} does not fit bbox {target}.",
                retryable=False,
            )
        return result

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

    def convert_preset(
        self, source: Path, destination: Path, *, preset: str, timeout: float = DEFAULT_TIMEOUT
    ) -> Path:
        def scale(width: int, height: int) -> str:
            return (
                f"scale='min({width},iw)':'min({height},ih)':force_original_aspect_ratio=decrease"
            )

        profiles = {
            "gif": ["-vf", f"fps=10,{scale(480, 480)}", "-an", "-loop", "0"],
            "webp": [
                "-vf",
                f"fps=12,{scale(512, 512)}",
                "-an",
                "-c:v",
                "libwebp_anim",
                "-loop",
                "0",
            ],
            "sticker": [
                "-t",
                "3",
                "-vf",
                f"fps=12,{scale(512, 512)},"
                "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000,format=yuva420p",
                "-an",
                "-c:v",
                "libwebp_anim",
                "-loop",
                "0",
                "-quality",
                "70",
            ],
            "mobile": [
                "-vf",
                f"{scale(1280, 720)}:force_divisible_by=2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
            ],
        }
        if preset not in profiles:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT, "Unknown media preset.", retryable=False
            )
        result = self._run(source, destination, profiles[preset], timeout=timeout)
        probe = self.validate(result)
        video = probe.video_stream
        if video is None or (preset != "mobile" and probe.has_audio):
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED, "Preset output streams are invalid.", retryable=False
            )
        if preset == "sticker" and (
            video.width != 512 or video.height != 512 or result.stat().st_size > 500_000
        ):
            _LOGGER.warning(
                "sticker_limits_exceeded width=%s height=%s size_bytes=%s",
                video.width,
                video.height,
                result.stat().st_size,
            )
            result.unlink(missing_ok=True)
            raise ExtractionError(
                ErrorCode.VALIDATION_FAILED, "Sticker exceeds 512x512 or 500 KB.", retryable=False
            )
        return result

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
        return self._with_decoded_dims(path, probe, timeout=timeout)

    @staticmethod
    def _with_decoded_dims(path: Path, probe: MediaProbe, *, timeout: float) -> MediaProbe:
        """Fill video dims ffprobe reports as unknown from decoded frames.

        Some ffprobe builds report width/height 0 (normalized to None) for
        codecs whose container carries no usable dims (e.g. animated WebP on
        older builds). The decoder always knows the real frame size, so a
        single showinfo frame is ground truth. Anything unparseable stays
        None (fail closed: callers treat unknown dims as a breach).
        """
        if not any(
            s.kind is StreamKind.VIDEO and (s.width is None or s.height is None)
            for s in probe.streams
        ):
            return probe
        dims = _decoded_frame_dims(path, timeout=timeout)
        if dims is None:
            return probe
        width, height = dims
        streams = tuple(
            replace(s, width=s.width or width, height=s.height or height)
            if s.kind is StreamKind.VIDEO and (s.width is None or s.height is None)
            else s
            for s in probe.streams
        )
        return replace(probe, streams=streams)

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
        try:
            self.validate(destination, timeout=30.0)
        except ExtractionError:
            destination.unlink(missing_ok=True)
            raise
        return destination


def _trim_args(start: float, end: float) -> list[str]:
    return ["-ss", f"{start:.3f}", "-t", f"{end - start:.3f}"]


def _cpu_args(video_codec: str) -> list[str]:
    if video_codec == "libvpx-vp9":
        return ["-deadline", "good", "-cpu-used", "4"]
    if video_codec == "libsvtav1":
        return ["-preset", "4"]
    return ["-preset", "veryfast"]


def _decoded_frame_dims(path: Path, *, timeout: float) -> tuple[int, int] | None:
    """Dimensions of the first decoded frame, or None when unknowable.

    Ground truth when container probing reports unknown dims: the decoder
    always sees real pixels. Never raises; callers fail closed on None.
    """
    try:
        completed = subprocess.run(
            [
                *ffmpeg_argv(),
                # info, not error: the showinfo frame lines this parses live
                # at info level and -v error would suppress them.
                "-v",
                "info",
                "-i",
                str(path),
                "-vf",
                "showinfo",
                "-vframes",
                "1",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if completed.returncode != 0:
        _LOGGER.warning(
            "decode_dims_failed rc=%s stderr=%s",
            completed.returncode,
            (completed.stderr or "")[-300:],
        )
        return None
    match = _DECODED_DIMS.search(completed.stderr or "")
    if match is None:
        _LOGGER.warning("decode_dims_unparsed stderr=%s", (completed.stderr or "")[-300:])
        return None
    try:
        width, height = int(match.group(1)), int(match.group(2))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _scale_filter(target: str) -> str:
    """Closed scale filter for a validated resize target."""
    if target.endswith("p"):
        return f"scale=-2:{target[:-1]}"
    return f"scale={target.lower()}:force_original_aspect_ratio=decrease:force_divisible_by=2"


def _crop_filter(box: str) -> str:
    """Closed crop filter for a validated crop box (ffmpeg takes w:h:x:y)."""
    size, _, offset = box.lower().partition("+")
    width, _, height = size.partition("x")
    if not offset:
        return f"crop={width}:{height}"
    return f"crop={width}:{height}:{offset.replace('+', ':')}"


def _crop_size(box: str) -> tuple[int, int]:
    size = box.lower().partition("+")[0]
    width, _, height = size.partition("x")
    try:
        return int(width), int(height)
    except ValueError:  # pragma: no cover — parse_crop validates the box
        raise ExtractionError(
            ErrorCode.VALIDATION_FAILED,
            f"Invalid crop box {box!r}.",
            retryable=False,
        ) from None


def _video_filter_args(
    resize_target: str | None, crop_box: str | None, framerate: str | None = None
) -> list[str]:
    """Build the single-pass geometry filter chain (crop before scale)."""
    chain: list[str] = []
    if crop_box is not None:
        chain.append(_crop_filter(crop_box))
    if resize_target is not None:
        chain.append(_scale_filter(resize_target))
    if framerate is not None:
        chain.append(f"fps={framerate}")
    if not chain:
        return []
    return ["-vf", ",".join(chain)]

"""User output intent.

This is the only shape the API accepts from the client: a small, typed model.
It is deliberately NOT a command line — there is no field that could carry an
arbitrary ffmpeg/yt-dlp argument (TECHNICAL_SPEC §5, §238). Unknown keys are
rejected on deserialization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ErrorCode, ExtractionError

_MEDIA = ("video", "audio")
_QUALITY = ("best", "worst")
_AUDIO = ("include", "remove", "only")
_VIDEO_CONTAINERS = ("mp4", "mkv", "webm", "gif", "webp", "sticker", "mobile")
_AUDIO_CONTAINERS = ("mp3", "m4a", "opus", "wav")
_CONTAINERS = _VIDEO_CONTAINERS + _AUDIO_CONTAINERS

_ALLOWED_KEYS = {
    "media",
    "quality",
    "container",
    "audio",
    "video_codec",
    "video_bitrate",
    "video_framerate",
    "processing",
    "audio_normalize",
    "subtitles",
    "metadata",
}
_VIDEO_CODECS = ("source", "h264", "vp9", "av1")
_PROCESSING_KEYS = {"resize", "trim", "crop"}
_PLAIN_SECONDS = re.compile(r"\d{1,5}(?:\.\d{1,3})?")
_CLOCK = re.compile(r"(?:(\d{1,2}):)?([0-5]?\d):([0-5]?\d(?:\.\d{1,3})?)")
_MAX_TRIM_SECONDS = 86_400.0
_HEIGHT_RE = re.compile(r"^(\d{2,4})p$")
_DIMENSIONS_RE = re.compile(r"^(\d{2,5})x(\d{2,5})$")
_MAX_RESIZE_HEIGHT = 4320
_MAX_RESIZE_DIMENSION = 8192
_CROP_BOX_RE = re.compile(r"^(\d{2,5})x(\d{2,5})$")
_CROP_OFFSET_BOX_RE = re.compile(r"^(\d{2,5})x(\d{2,5})\+(\d{1,5})\+(\d{1,5})$")
_MAX_CROP_DIMENSION = 8192
_CROP_MESSAGE = "processing.crop must look like '640x480' or '640x480+100+50'"
_BITRATE_RE = re.compile(r"^\d{2,5}k$")
_MAX_BITRATE_KB = 64_000
_MIN_BITRATE_KB = 64
_FRAMERATE_RE = re.compile(r"^\d{1,3}(?:\.\d{1,2})?$")
_MAX_FRAMERATE = 120.0


class MediaChoice(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"


class QualityChoice(StrEnum):
    BEST = "best"
    WORST = "worst"


class AudioChoice(StrEnum):
    INCLUDE = "include"
    REMOVE = "remove"
    ONLY = "only"


@dataclass(frozen=True, slots=True)
class Processing:
    resize: str | None = None
    trim: str | None = None
    crop: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {"resize": self.resize, "trim": self.trim, "crop": self.crop}


def parse_resize(value: str) -> str:
    """Parse ``720p`` or ``1280x720`` into a normalized resize target.

    Returns the validated string lowercased — the planner and adapter decide
    how to interpret it. Only closed formats are accepted: height ``Np``
    (case-insensitive ``p``, 1..4320) or dimensions ``WxH`` (lowercase ``x``
    only, each side 1..8192). Absurd sizes like ``99999x99999`` are rejected
    here, fail-fast, before any tool is invoked.
    """
    raw = value.strip()
    lowered = raw.lower()
    if _HEIGHT_RE.fullmatch(lowered):
        height = int(lowered[:-1])
        if 1 <= height <= _MAX_RESIZE_HEIGHT:
            return lowered
        raise _bad("processing.resize must look like '720p' or '1280x720'")
    if _DIMENSIONS_RE.fullmatch(raw):
        width, height = (int(part) for part in lowered.split("x"))
        if 1 <= width <= _MAX_RESIZE_DIMENSION and 1 <= height <= _MAX_RESIZE_DIMENSION:
            return lowered
        raise _bad("processing.resize must look like '720p' or '1280x720'")
    raise _bad("processing.resize must look like '720p' or '1280x720'")


def parse_crop(value: str) -> str:
    """Parse ``WxH`` or ``WxH+X+Y`` into a normalized crop box.

    Unlike :func:`parse_resize`, a crop box is EXACT, not a bounding box: the
    adapter keeps precisely the requested rectangle. Offsets are non-negative
    (a negative origin would silently pad with black). Both sides must be even
    and within 2..8192 — odd crop sizes cannot be encoded by the H.264/VP9
    yuv420p pixel format used by every video target, so rejecting them here is
    more honest than failing inside ffmpeg.
    """
    raw = value.strip().lower()
    offset = _CROP_OFFSET_BOX_RE.fullmatch(raw)
    if offset is not None:
        width, height, x, y = (int(part) for part in offset.groups())
        valid_offset = x <= _MAX_CROP_DIMENSION and y <= _MAX_CROP_DIMENSION
        if valid_offset and _valid_crop_size(width, height):
            return f"{width}x{height}+{x}+{y}"
        raise _bad(_CROP_MESSAGE)
    box = _CROP_BOX_RE.fullmatch(raw)
    if box is not None:
        width, height = (int(part) for part in box.groups())
        if _valid_crop_size(width, height):
            return f"{width}x{height}"
    raise _bad(_CROP_MESSAGE)


def _valid_crop_size(width: int, height: int) -> bool:
    return (
        2 <= width <= _MAX_CROP_DIMENSION
        and 2 <= height <= _MAX_CROP_DIMENSION
        and width % 2 == 0
        and height % 2 == 0
    )


@dataclass(frozen=True, slots=True)
class OutputIntent:
    media: MediaChoice
    quality: QualityChoice
    container: str
    audio: AudioChoice
    video_codec: str  # "source", "h264", "vp9" or "av1"
    processing: Processing = Processing()
    video_bitrate: str | None = None
    video_framerate: str | None = None
    audio_normalize: bool = False
    subtitles: bool = False
    metadata: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "media": self.media.value,
            "quality": self.quality.value,
            "container": self.container,
            "audio": self.audio.value,
            "video_codec": self.video_codec,
            "video_bitrate": self.video_bitrate,
            "video_framerate": self.video_framerate,
            "processing": self.processing.as_dict(),
            "audio_normalize": self.audio_normalize,
            "subtitles": self.subtitles,
            "metadata": self.metadata,
        }


def parse_intent(payload: Any) -> OutputIntent:
    """Validate a client payload into an :class:`OutputIntent`.

    Everything that does not fit the closed schema is rejected here, before
    any tool is invoked. Raises :class:`ExtractionError` with
    ``UNSUPPORTED_INTENT``.
    """
    if not isinstance(payload, dict):
        raise _bad("intent must be a JSON object")
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise _bad(f"unknown intent keys: {sorted(unknown)}")
    media_raw = payload.get("media")
    if media_raw not in _MEDIA:
        raise _bad(f"media must be one of {_MEDIA}")
    quality_raw = payload.get("quality")
    if quality_raw not in _QUALITY:
        raise _bad(f"quality must be one of {_QUALITY}")
    container = payload.get("container")
    if not isinstance(container, str) or container.lower() not in _CONTAINERS:
        raise _bad(f"container must be one of {_CONTAINERS}")
    container = container.lower()
    audio_raw = payload.get("audio")
    if audio_raw not in _AUDIO:
        raise _bad(f"audio must be one of {_AUDIO}")
    video_codec = payload.get("video_codec", "source")
    if video_codec not in _VIDEO_CODECS:
        raise _bad(f"video_codec must be one of {_VIDEO_CODECS}")
    video_bitrate = payload.get("video_bitrate")
    if video_bitrate is not None:
        if not isinstance(video_bitrate, str):
            raise _bad("video_bitrate must be a string like '2500k'")
        parse_video_bitrate(video_bitrate)
    video_framerate = payload.get("video_framerate")
    if video_framerate is not None:
        if not isinstance(video_framerate, str):
            raise _bad("video_framerate must be a string like '30'")
        parse_video_framerate(video_framerate)
    audio_normalize = payload.get("audio_normalize", False)
    if not isinstance(audio_normalize, bool):
        raise _bad("audio_normalize must be a boolean")
    subtitles = payload.get("subtitles", False)
    if not isinstance(subtitles, bool):
        raise _bad("subtitles must be a boolean")
    metadata = payload.get("metadata", False)
    if not isinstance(metadata, bool):
        raise _bad("metadata must be a boolean")
    processing = payload.get("processing") or {}
    if not isinstance(processing, dict):
        raise _bad("processing must be an object")
    unknown_p = set(processing) - _PROCESSING_KEYS
    if unknown_p:
        raise _bad(f"unknown processing keys: {sorted(unknown_p)}")
    resize = processing.get("resize")
    trim = processing.get("trim")
    crop = processing.get("crop")
    if resize is not None:
        if not isinstance(resize, str):
            raise _bad("processing.resize must be a string like '720p'")
        parse_resize(resize)
    if crop is not None:
        if not isinstance(crop, str):
            raise _bad("processing.crop must be a string like '640x480'")
        parse_crop(crop)
    if trim is not None and not isinstance(trim, str):
        raise _bad("processing.trim must be a string like '00:10-00:20'")
    if trim is not None:
        parse_trim(trim)
    media = MediaChoice(media_raw)
    audio = AudioChoice(audio_raw)
    detected = _classify_container(container)
    if media is MediaChoice.AUDIO and detected != "audio":
        raise _bad(f"container {container!r} does not carry audio")
    if media is MediaChoice.VIDEO and detected != "video":
        raise _bad(f"container {container!r} is not a video container")
    if audio is AudioChoice.ONLY and media is MediaChoice.VIDEO:
        raise _bad('audio="only" requires media="audio"')
    if container in {"gif", "webp", "sticker"} and audio is not AudioChoice.REMOVE:
        raise _bad(f"{container} requires audio=remove")
    if container == "mobile" and audio is not AudioChoice.INCLUDE:
        raise _bad("mobile requires audio=include")
    if media is MediaChoice.AUDIO and audio is not AudioChoice.ONLY:
        raise _bad('media="audio" requires audio="only"')
    return OutputIntent(
        media=media,
        quality=QualityChoice(quality_raw),
        container=container,
        audio=audio,
        video_codec=video_codec,
        processing=Processing(resize=resize, trim=trim, crop=crop),
        video_bitrate=video_bitrate,
        video_framerate=video_framerate,
        audio_normalize=audio_normalize,
        subtitles=subtitles,
        metadata=metadata,
    )


def parse_video_bitrate(value: str) -> str:
    """Parse ``2500k`` into a normalized bitrate (``64k``..``64000k``)."""
    raw = value.strip().lower()
    if _BITRATE_RE.fullmatch(raw):
        kb = int(raw[:-1])
        if _MIN_BITRATE_KB <= kb <= _MAX_BITRATE_KB:
            return f"{kb}k"
    raise _bad("video_bitrate must look like '2500k' (64k..64000k)")


def parse_video_framerate(value: str) -> str:
    """Parse ``30`` or ``29.97`` into a normalized framerate (1..120)."""
    raw = value.strip()
    if _FRAMERATE_RE.fullmatch(raw):
        fps = float(raw)
        if 0 < fps <= _MAX_FRAMERATE:
            return raw
    raise _bad("video_framerate must look like '30' or '29.97' (1..120)")


def parse_trim(value: str) -> tuple[float, float]:
    """Parse ``START-END`` into ``(start, end)`` seconds.

    Each bound is ``MM:SS``, ``HH:MM:SS`` (optionally with ``.mmm``) or plain
    seconds. Nothing but numbers ever reaches the tool argv.
    """
    parts = value.strip().split("-")
    if len(parts) != 2:
        raise _bad("processing.trim must look like '00:10-00:20'")
    start = _parse_timestamp(parts[0])
    end = _parse_timestamp(parts[1])
    if end <= start:
        raise _bad("processing.trim end must be after start")
    if end - start > _MAX_TRIM_SECONDS:
        raise _bad("processing.trim range is too long")
    return start, end


def _parse_timestamp(raw: str) -> float:
    text = raw.strip()
    if _PLAIN_SECONDS.fullmatch(text):
        return float(text)
    clock = _CLOCK.fullmatch(text)
    if clock is None:
        raise _bad("processing.trim bounds must be seconds, MM:SS or HH:MM:SS")
    hours, minutes, seconds = clock.group(1), clock.group(2), clock.group(3)
    return int(hours or 0) * 3600 + int(minutes) * 60 + float(seconds)


def _classify_container(container: str) -> str:
    return "audio" if container in _AUDIO_CONTAINERS else "video"


def _bad(message: str) -> ExtractionError:
    return ExtractionError(
        ErrorCode.UNSUPPORTED_INTENT,
        message,
        retryable=False,
    )

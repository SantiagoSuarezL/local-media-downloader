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

_ALLOWED_KEYS = {"media", "quality", "container", "audio", "video_codec", "processing"}
_PROCESSING_KEYS = {"resize", "trim"}
_PLAIN_SECONDS = re.compile(r"\d{1,5}(?:\.\d{1,3})?")
_CLOCK = re.compile(r"(?:(\d{1,2}):)?([0-5]?\d):([0-5]?\d(?:\.\d{1,3})?)")
_MAX_TRIM_SECONDS = 86_400.0


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

    def as_dict(self) -> dict[str, object]:
        return {"resize": self.resize, "trim": self.trim}


@dataclass(frozen=True, slots=True)
class OutputIntent:
    media: MediaChoice
    quality: QualityChoice
    container: str
    audio: AudioChoice
    video_codec: str  # only "source" is accepted until Phase 14 presets
    processing: Processing = Processing()

    def as_dict(self) -> dict[str, object]:
        return {
            "media": self.media.value,
            "quality": self.quality.value,
            "container": self.container,
            "audio": self.audio.value,
            "video_codec": self.video_codec,
            "processing": self.processing.as_dict(),
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
    if video_codec != "source":
        raise _bad('only video_codec="source" is supported')
    processing = payload.get("processing") or {}
    if not isinstance(processing, dict):
        raise _bad("processing must be an object")
    unknown_p = set(processing) - _PROCESSING_KEYS
    if unknown_p:
        raise _bad(f"unknown processing keys: {sorted(unknown_p)}")
    resize = processing.get("resize")
    trim = processing.get("trim")
    if resize is not None and not isinstance(resize, str):
        raise _bad("processing.resize must be a string like '720p'")
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
        processing=Processing(resize=resize, trim=trim),
    )


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

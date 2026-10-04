"""Normalized media model.

This is the contract the rest of the application speaks. It is deliberately
free of any yt-dlp shapes: the adapter translates, the domain never sees raw
extractor JSON (TECHNICAL_SPEC §1, ARCHITECTURE §24).

Absence is represented with ``None``, never with a fake value
(TECHNICAL_SPEC §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FormatKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    COMBINED = "combined"


@dataclass(frozen=True, slots=True)
class MediaFormat:
    """One selectable representation of the source media."""

    id: str
    kind: FormatKind
    container: str | None
    extension: str | None
    video_codec: str | None
    audio_codec: str | None
    width: int | None
    height: int | None
    fps: float | None
    bitrate: int | None
    audio_bitrate: int | None
    filesize: int | None
    filesize_approx: bool
    dynamic_range: str | None
    protocol: str | None
    has_video: bool
    has_audio: bool
    quality_score: float
    note: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "container": self.container,
            "extension": self.extension,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "bitrate": self.bitrate,
            "audio_bitrate": self.audio_bitrate,
            "filesize": self.filesize,
            "filesize_approx": self.filesize_approx,
            "dynamic_range": self.dynamic_range,
            "protocol": self.protocol,
            "has_video": self.has_video,
            "has_audio": self.has_audio,
            "quality_score": self.quality_score,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class MediaSource:
    """Where the media comes from.

    ``extractor_key`` is yt-dlp's internal extractor class name. It is kept for
    diagnostics but deliberately excluded from the public API payload.
    """

    url: str
    extractor: str | None
    extractor_key: str | None
    title: str | None
    uploader: str | None


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """Normalized result of resolving a URL."""

    source: MediaSource
    id: str
    duration_seconds: float | None
    thumbnail_url: str | None
    is_live: bool
    formats: tuple[MediaFormat, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source": {
                "url": self.source.url,
                "extractor": self.source.extractor,
                "title": self.source.title,
                "uploader": self.source.uploader,
            },
            "duration_seconds": self.duration_seconds,
            "thumbnail_url": self.thumbnail_url,
            "is_live": self.is_live,
            "formats": [f.as_dict() for f in self.formats],
            "warnings": list(self.warnings),
        }

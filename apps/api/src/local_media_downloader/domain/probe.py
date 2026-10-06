"""Normalized result of probing a local media file.

This is the contract the rest of the application speaks for FFprobe output.
It is deliberately free of FFprobe's raw JSON shapes: the adapter translates,
the domain never sees the tool schema (TECHNICAL_SPEC §1, ARCHITECTURE §24).

Absence is represented with ``None``, never with a fake value
(TECHNICAL_SPEC §4): a direct media link or a broken file reports
``duration_seconds=None``, not a fabricated 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class StreamKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class StreamProbe:
    """One stream inside a media container."""

    index: int
    kind: StreamKind
    codec_name: str | None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    bitrate: int | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "kind": self.kind.value,
            "codec_name": self.codec_name,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bitrate": self.bitrate,
        }


@dataclass(frozen=True, slots=True)
class MediaProbe:
    """Normalized description of a local media file."""

    path: str
    container: str | None
    duration_seconds: float | None
    size_bytes: int | None
    bitrate: int | None
    streams: tuple[StreamProbe, ...] = field(default_factory=tuple)

    @property
    def has_video(self) -> bool:
        return any(s.kind is StreamKind.VIDEO for s in self.streams)

    @property
    def has_audio(self) -> bool:
        return any(s.kind is StreamKind.AUDIO for s in self.streams)

    @property
    def video_stream(self) -> StreamProbe | None:
        for stream in self.streams:
            if stream.kind is StreamKind.VIDEO:
                return stream
        return None

    @property
    def audio_stream(self) -> StreamProbe | None:
        for stream in self.streams:
            if stream.kind is StreamKind.AUDIO:
                return stream
        return None

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "container": self.container,
            "duration_seconds": self.duration_seconds,
            "size_bytes": self.size_bytes,
            "bitrate": self.bitrate,
            "has_video": self.has_video,
            "has_audio": self.has_audio,
            "streams": [s.as_dict() for s in self.streams],
        }

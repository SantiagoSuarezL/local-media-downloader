"""Translation from raw yt-dlp JSON into the normalized domain model.

This is the only place that knows yt-dlp's schema. Everything downstream sees
``MediaInfo``/``MediaFormat`` (TECHNICAL_SPEC §1, ARCHITECTURE §24).
"""

from __future__ import annotations

from typing import Any

from ..domain.media import FormatKind, MediaFormat, MediaInfo, MediaSource

_NONE_TOKENS = {"none", "unknown", ""}
# Containers that only make sense for one kind of stream.
_AUDIO_ONLY_EXTENSIONS = {"m4a", "mp3", "opus", "ogg", "aac", "wav", "flac", "weba"}
# Containers that carry video. A direct media link (the generic extractor) often
# reports no codec information at all; the container still tells us the payload
# is video, and the missing codec detail is flagged so FFprobe can confirm it in
# Phase 4 instead of the adapter inventing it.
_VIDEO_CONTAINERS = {
    "mp4",
    "m4v",
    "webm",
    "mkv",
    "mov",
    "avi",
    "flv",
    "ts",
    "m2ts",
    "ogv",
    "3gp",
}

# Small, deliberately close bases: they break near-ties (combined beats
# video-only of equal quality, video beats audio-only) without ever letting a
# convenience outrank a resolution difference.
_KIND_BASE: dict[FormatKind, float] = {
    FormatKind.COMBINED: 105.0,
    FormatKind.VIDEO: 100.0,
    FormatKind.AUDIO: 50.0,
}


def _clean_codec(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return None if text.lower() in _NONE_TOKENS else text


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _as_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _classify(
    video_codec: str | None, audio_codec: str | None, extension: str | None
) -> FormatKind | None:
    has_video = video_codec is not None
    has_audio = audio_codec is not None
    if has_video and has_audio:
        return FormatKind.COMBINED
    if has_video:
        return FormatKind.VIDEO
    if has_audio:
        return FormatKind.AUDIO
    if not extension:
        return None
    container = extension.lower()
    if container in _AUDIO_ONLY_EXTENSIONS:
        return FormatKind.AUDIO
    if container in _VIDEO_CONTAINERS:
        return FormatKind.VIDEO
    return None


def quality_score(
    kind: FormatKind,
    *,
    height: int | None,
    fps: float | None,
    video_bitrate: int | None,
    audio_bitrate: int | None,
) -> float:
    """Heuristic ordering score used only to sort candidates for the planner.

    It expresses "how good is this representation of the source", never a
    quality the source does not have. A 720p source scores lower than a 1080p
    one; nothing here can invent resolution (ENGINEERING_PRINCIPLES #6).

    Resolution dominates on purpose. Being a combined format is a convenience,
    not quality, so it only wins near-ties — otherwise a 360p muxed file would
    outrank a 1080p video-only stream, which is exactly the "fake maximum
    quality" failure the spec warns about.
    """
    score = _KIND_BASE[kind]
    if height:
        score += min(height, 4320) / 10.0
    if fps:
        score += min(fps, 240.0) / 20.0
    if video_bitrate:
        score += min(video_bitrate, 50_000_000) / 200_000.0
    if audio_bitrate:
        score += min(audio_bitrate, 1_000_000) / 50_000.0
    return round(score, 3)


def normalize_format(raw: dict[str, Any]) -> MediaFormat | None:
    # A format without an id cannot be selected later, so it is dropped here
    # rather than surfacing as an unusable entry.
    format_id = str(raw.get("format_id") or "").strip()
    if not format_id:
        return None

    video_codec = _clean_codec(raw.get("vcodec"))
    audio_codec = _clean_codec(raw.get("acodec"))
    extension = _as_str(raw.get("ext"))
    kind = _classify(video_codec, audio_codec, extension)
    if kind is None:
        return None

    height = _as_int(raw.get("height"))
    fps = _as_float(raw.get("fps"))
    video_bitrate = _as_int(raw.get("tbr")) or _as_int(raw.get("vbr"))
    audio_bitrate = _as_int(raw.get("abr"))
    filesize = _as_int(raw.get("filesize"))
    filesize_approx = filesize is None and _as_int(raw.get("filesize_approx")) is not None

    has_video = video_codec is not None or kind in (FormatKind.VIDEO, FormatKind.COMBINED)
    has_audio = audio_codec is not None or kind in (FormatKind.AUDIO, FormatKind.COMBINED)

    return MediaFormat(
        id=format_id,
        kind=kind,
        container=_as_str(raw.get("container")),
        extension=extension,
        video_codec=video_codec,
        audio_codec=audio_codec,
        width=_as_int(raw.get("width")),
        height=height,
        fps=fps,
        bitrate=video_bitrate,
        audio_bitrate=audio_bitrate,
        filesize=filesize,
        filesize_approx=filesize_approx,
        dynamic_range=_as_str(raw.get("dynamic_range")),
        protocol=_as_str(raw.get("protocol")),
        has_video=has_video,
        has_audio=has_audio,
        quality_score=quality_score(
            kind,
            height=height,
            fps=fps,
            video_bitrate=video_bitrate,
            audio_bitrate=audio_bitrate,
        ),
        note=_as_str(raw.get("format_note")),
    )


def normalize(raw: dict[str, Any], *, requested_url: str) -> MediaInfo:
    formats: list[MediaFormat] = []
    for entry in raw.get("formats") or []:
        if not isinstance(entry, dict):
            continue
        normalized = normalize_format(entry)
        if normalized is not None:
            formats.append(normalized)
    formats.sort(key=lambda f: f.quality_score, reverse=True)

    warnings: list[str] = []
    is_live = bool(raw.get("is_live"))
    if is_live:
        warnings.append("This source is a live stream.")
    if not formats:
        warnings.append("The source reported no usable formats.")
    if any(
        (f.has_video and f.video_codec is None) or (f.has_audio and f.audio_codec is None)
        for f in formats
    ):
        # Direct media links report no codec details. Claiming a capability here
        # would be fake, so the consumer is told to confirm it with FFprobe.
        warnings.append(
            "Codec information is unavailable for at least one format; "
            "stream details must be confirmed by probing the media."
        )

    return MediaInfo(
        source=MediaSource(
            url=_as_str(raw.get("webpage_url")) or requested_url,
            extractor=_as_str(raw.get("extractor")),
            extractor_key=_as_str(raw.get("extractor_key")),
            title=_as_str(raw.get("title")),
            uploader=_as_str(raw.get("uploader") or raw.get("channel")),
        ),
        id=str(raw.get("id") or ""),
        duration_seconds=_as_float(raw.get("duration")),
        thumbnail_url=_as_str(raw.get("thumbnail")),
        is_live=is_live,
        formats=tuple(formats),
        warnings=tuple(warnings),
    )

"""Execution planner.

Translates a validated :class:`OutputIntent` plus the resolved
:class:`MediaInfo` into an :class:`ExecutionPlan`. Rules, in order:

1. stream copy (remux) is preferred and transcoding only happens when the
   source container/codecs cannot satisfy the intent directly
   (ENGINEERING_PRINCIPLES #84);
2. audio-only intent always maps to an audio extraction step;
3. ``audio="remove"`` maps to a video-only stream-copy when compatible;
4. processing: trim, crop and resize are planned as an accurate re-encode (stream
   copy can neither cut on non-keyframes nor change the pixel geometry); audio
   normalization re-encodes the audio track (loudnorm is a filter, not a copy),
   so it forces a transcode the same way. All of them are rejected for media
   presets, audio-removed output and live sources — an intent must never
   silently degrade (PRD: fake features are worse than rejected intents);
5. the plan contains tool steps and static detail only — user input can
   never inject command arguments (TECHNICAL_SPEC §258).
"""

from __future__ import annotations

from ..domain.errors import ErrorCode, ExtractionError
from ..domain.intent import (
    AudioChoice,
    MediaChoice,
    OutputIntent,
    parse_crop,
    parse_resize,
    parse_trim,
    parse_video_bitrate,
    parse_video_framerate,
)
from ..domain.media import MediaInfo
from ..domain.plan import ExecutionPlan, PlanStep

# Which source containers/codecs a target container can hold without
# re-encoding. Unknown sources force a transcode, never a broken copy.
_CONTAINER_ACCEPTS: dict[str, frozenset[str]] = {
    "mp4": frozenset({"mp4", "m4v", "mov", "isom"}),
    "mkv": frozenset({"mkv", "matroska", "webm", "mp4", "m4v", "mov", "avi", "flv", "mpeg", "3gp"}),
    "webm": frozenset({"webm"}),
}

_AUDIO_CODEC_FOR_CONTAINER = {
    "mp3": "libmp3lame",
    "m4a": "aac",
    "opus": "libopus",
    "wav": "pcm_s16le",
}

# Intent codec choice → ffmpeg encoder, and which containers may hold it.
# Unknown pairs are rejected (UNSUPPORTED_INTENT) instead of letting ffmpeg
# produce a stream the container cannot carry.
_VIDEO_ENCODER_FOR_CODEC = {
    "h264": "libx264",
    "vp9": "libvpx-vp9",
    "av1": "libsvtav1",
}
_CONTAINERS_FOR_CODEC = {
    "h264": frozenset({"mp4", "mkv"}),
    "vp9": frozenset({"webm", "mkv"}),
    "av1": frozenset({"mp4", "mkv", "webm"}),
}


class Planner:
    def plan(self, intent: OutputIntent, info: MediaInfo) -> ExecutionPlan:
        if not info.formats:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "No usable formats were resolved for this source.",
                retryable=False,
            )
        if intent.subtitles:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Subtitle extraction is not supported yet.",
                retryable=False,
            )
        if intent.metadata:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Metadata editing is not supported yet.",
                retryable=False,
            )

        source_container = _primary_container(info)
        trim = self._trim_detail(intent, info)
        resize = self._resize_detail(intent, info)
        crop = self._crop_detail(intent, info)
        encode = self._encode_detail(intent, info)

        if intent.container in {"gif", "webp", "sticker", "mobile"}:
            if trim:
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "Trim is not supported together with media presets.",
                    retryable=False,
                )
            if encode:
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "Video encode options are not supported together with media presets.",
                    retryable=False,
                )
            if intent.audio_normalize:
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "Audio normalization is not supported together with media presets.",
                    retryable=False,
                )
            if not any(fmt.has_video for fmt in info.formats):
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "This preset requires a video source.",
                    retryable=False,
                )
            container = (
                "mp4"
                if intent.container == "mobile"
                else ("webp" if intent.container == "sticker" else intent.container)
            )
            return ExecutionPlan(
                steps=(
                    PlanStep(
                        "SELECT_FORMAT",
                        "yt_dlp",
                        {"selector": self._selector(intent, audio_only=False)},
                    ),
                    PlanStep("DOWNLOAD", "yt_dlp", {}),
                    PlanStep(
                        "CONVERT_PRESET",
                        "ffmpeg",
                        {"preset": intent.container, "container": container},
                    ),
                    PlanStep("VALIDATE", "ffprobe", {}),
                    PlanStep("FINALIZE", "internal", {}),
                ),
                strategy="transcode",
            )

        if intent.media is MediaChoice.AUDIO:
            return self._audio_plan(intent, trim)

        if intent.audio is AudioChoice.ONLY:
            # parse_intent guarantees media=video never reaches here.
            return self._audio_plan(intent, trim)

        if intent.audio is AudioChoice.REMOVE:
            if intent.audio_normalize:
                # The output has no audio track: there is nothing to normalize,
                # and a silent no-op would fake the feature (PRD).
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "Audio normalization requires an audio track in the output.",
                    retryable=False,
                )
            return self._video_only_plan(intent, source_container, trim, resize, crop, encode)

        return self._full_video_plan(intent, source_container, trim, resize, crop, encode)

    def _trim_detail(self, intent: OutputIntent, info: MediaInfo) -> dict[str, str]:
        if intent.processing.trim is None:
            return {}
        if info.is_live:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Trim is not supported for live sources.",
                retryable=False,
            )
        start, end = parse_trim(intent.processing.trim)
        if info.duration_seconds is not None and start >= info.duration_seconds:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Trim start is beyond the end of the media.",
                retryable=False,
            )
        return {"trim_start": f"{start:.3f}", "trim_end": f"{end:.3f}"}

    def _resize_detail(self, intent: OutputIntent, info: MediaInfo) -> dict[str, str]:
        if intent.processing.resize is None:
            return {}
        if info.is_live:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Resize is not supported for live sources.",
                retryable=False,
            )
        if intent.container in {"gif", "webp", "sticker", "mobile"}:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Resize is not supported together with media presets.",
                retryable=False,
            )
        if (
            intent.container in {"mp3", "m4a", "opus", "wav"}
            or intent.media is MediaChoice.AUDIO
            or intent.audio is AudioChoice.ONLY
        ):
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Resize is not supported for audio-only output.",
                retryable=False,
            )
        resize = parse_resize(intent.processing.resize)
        return {"resize": resize}

    def _crop_detail(self, intent: OutputIntent, info: MediaInfo) -> dict[str, str]:
        if intent.processing.crop is None:
            return {}
        if info.is_live:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Crop is not supported for live sources.",
                retryable=False,
            )
        if intent.container in {"gif", "webp", "sticker", "mobile"}:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Crop is not supported together with media presets.",
                retryable=False,
            )
        if (
            intent.container in {"mp3", "m4a", "opus", "wav"}
            or intent.media is MediaChoice.AUDIO
            or intent.audio is AudioChoice.ONLY
        ):
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Crop is not supported for audio-only output.",
                retryable=False,
            )
        crop = parse_crop(intent.processing.crop)
        return {"crop": crop}

    def _encode_detail(self, intent: OutputIntent, info: MediaInfo) -> dict[str, str]:
        if (
            intent.video_codec == "source"
            and intent.video_bitrate is None
            and intent.video_framerate is None
        ):
            return {}
        if info.is_live:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Video encode options are not supported for live sources.",
                retryable=False,
            )
        if intent.container in {"gif", "webp", "sticker", "mobile"}:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Video encode options are not supported together with media presets.",
                retryable=False,
            )
        if intent.media is MediaChoice.AUDIO or intent.audio is AudioChoice.ONLY:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Video encode options are not supported for audio-only output.",
                retryable=False,
            )
        if intent.container in {"mp3", "m4a", "opus", "wav"}:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Video encode options are not supported for audio-only output.",
                retryable=False,
            )
        detail: dict[str, str] = {}
        if intent.video_codec != "source":
            if intent.container not in _CONTAINERS_FOR_CODEC[intent.video_codec]:
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    f"Codec {intent.video_codec} cannot be stored in {intent.container}.",
                    retryable=False,
                )
            detail["video_codec"] = _VIDEO_ENCODER_FOR_CODEC[intent.video_codec]
        if intent.video_bitrate is not None:
            detail["bitrate"] = parse_video_bitrate(intent.video_bitrate)
        if intent.video_framerate is not None:
            detail["framerate"] = parse_video_framerate(intent.video_framerate)
        return detail

    def _selector(self, intent: OutputIntent, *, audio_only: bool) -> str:
        if audio_only:
            return "worstaudio" if intent.quality.value == "worst" else "bestaudio"
        return "worst" if intent.quality.value == "worst" else "bestvideo*+bestaudio/best"

    def _audio_plan(self, intent: OutputIntent, trim: dict[str, str]) -> ExecutionPlan:
        codec = _AUDIO_CODEC_FOR_CONTAINER[intent.container]
        steps = (
            PlanStep(
                "SELECT_FORMAT", "yt_dlp", {"selector": self._selector(intent, audio_only=True)}
            ),
            PlanStep("DOWNLOAD", "yt_dlp", {}),
            PlanStep(
                "EXTRACT_AUDIO",
                "ffmpeg",
                {
                    "codec": codec,
                    "container": intent.container,
                    **trim,
                    "audio_normalize": str(intent.audio_normalize),
                },
            ),
            PlanStep("VALIDATE", "ffprobe", {}),
            PlanStep("FINALIZE", "internal", {}),
        )
        return ExecutionPlan(steps=steps, strategy="extract_audio")

    def _video_only_plan(
        self,
        intent: OutputIntent,
        source_container: str | None,
        trim: dict[str, str],
        resize: dict[str, str],
        crop: dict[str, str],
        encode: dict[str, str],
    ) -> ExecutionPlan:
        compatible = (
            not trim
            and not resize
            and not crop
            and not encode
            and source_container is not None
            and source_container in _CONTAINER_ACCEPTS.get(intent.container, frozenset())
        )
        if compatible:
            steps = (
                PlanStep(
                    "SELECT_FORMAT",
                    "yt_dlp",
                    {"selector": self._selector(intent, audio_only=False)},
                ),
                PlanStep("DOWNLOAD", "yt_dlp", {}),
                PlanStep(
                    "VIDEO_ONLY", "ffmpeg", {"mode": "stream_copy", "container": intent.container}
                ),
                PlanStep("VALIDATE", "ffprobe", {}),
                PlanStep("FINALIZE", "internal", {}),
            )
        else:
            steps = (
                PlanStep(
                    "SELECT_FORMAT",
                    "yt_dlp",
                    {"selector": self._selector(intent, audio_only=False)},
                ),
                PlanStep("DOWNLOAD", "yt_dlp", {}),
                PlanStep(
                    "TRANSCODE",
                    "ffmpeg",
                    {
                        "video_codec": "libvpx-vp9" if intent.container == "webm" else "libx264",
                        "audio": "none",
                        "container": intent.container,
                        **trim,
                        **resize,
                        **crop,
                        **encode,
                    },
                ),
                PlanStep("VALIDATE", "ffprobe", {}),
                PlanStep("FINALIZE", "internal", {}),
            )
        return ExecutionPlan(steps=steps, strategy="video_only" if compatible else "transcode")

    def _full_video_plan(
        self,
        intent: OutputIntent,
        source_container: str | None,
        trim: dict[str, str],
        resize: dict[str, str],
        crop: dict[str, str],
        encode: dict[str, str],
    ) -> ExecutionPlan:
        compatible = (
            not trim
            and not resize
            and not crop
            and not encode
            and not intent.audio_normalize
            and source_container is not None
            and source_container in _CONTAINER_ACCEPTS.get(intent.container, frozenset())
        )
        if compatible:
            steps = (
                PlanStep(
                    "SELECT_FORMAT",
                    "yt_dlp",
                    {"selector": self._selector(intent, audio_only=False)},
                ),
                PlanStep("DOWNLOAD", "yt_dlp", {}),
                PlanStep("MERGE", "yt_dlp", {"mode": "mux"}),
                PlanStep("REMUX", "ffmpeg", {"mode": "stream_copy", "container": intent.container}),
                PlanStep("VALIDATE", "ffprobe", {}),
                PlanStep("FINALIZE", "internal", {}),
            )
        else:
            steps = (
                PlanStep(
                    "SELECT_FORMAT",
                    "yt_dlp",
                    {"selector": self._selector(intent, audio_only=False)},
                ),
                PlanStep("DOWNLOAD", "yt_dlp", {}),
                PlanStep("MERGE", "yt_dlp", {"mode": "mux"}),
                PlanStep(
                    "TRANSCODE",
                    "ffmpeg",
                    {
                        "video_codec": "libvpx-vp9" if intent.container == "webm" else "libx264",
                        "audio_codec": "libopus" if intent.container == "webm" else "aac",
                        "container": intent.container,
                        **trim,
                        **resize,
                        **crop,
                        **encode,
                        "audio_normalize": str(intent.audio_normalize),
                    },
                ),
                PlanStep("VALIDATE", "ffprobe", {}),
                PlanStep("FINALIZE", "internal", {}),
            )
        return ExecutionPlan(steps=steps, strategy="copy" if compatible else "transcode")


def _primary_container(info: MediaInfo) -> str | None:
    """Best-effort source container from the resolved formats."""
    containers = [f.container or f.extension for f in info.formats]
    containers = [c.lower() for c in containers if c]
    if not containers:
        return None
    return max(set(containers), key=containers.count)

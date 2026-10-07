"""Execution planner.

Translates a validated :class:`OutputIntent` plus the resolved
:class:`MediaInfo` into an :class:`ExecutionPlan`. Rules, in order:

1. stream copy (remux) is preferred and transcoding only happens when the
   source container/codecs cannot satisfy the intent directly
   (ENGINEERING_PRINCIPLES #84);
2. audio-only intent always maps to an audio extraction step;
3. ``audio="remove"`` maps to a video-only stream-copy when compatible;
4. processing (resize/trim) is rejected until Phase 14 implements it — an
   intent must never silently degrade (PRD: fake features are worse than
   rejected intents);
5. the plan contains tool steps and static detail only — user input can
   never inject command arguments (TECHNICAL_SPEC §258).
"""

from __future__ import annotations

from ..domain.errors import ErrorCode, ExtractionError
from ..domain.intent import AudioChoice, MediaChoice, OutputIntent
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


class Planner:
    def plan(self, intent: OutputIntent, info: MediaInfo) -> ExecutionPlan:
        if intent.processing.resize is not None or intent.processing.trim is not None:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "Resize/trim intents are not supported until Phase 14.",
                retryable=False,
            )
        if not info.formats:
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "No usable formats were resolved for this source.",
                retryable=False,
            )

        source_container = _primary_container(info)

        if intent.container in {"gif", "webp", "sticker", "mobile"}:
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
            return self._audio_plan(intent)

        if intent.audio is AudioChoice.ONLY:
            # parse_intent guarantees media=video never reaches here.
            return self._audio_plan(intent)

        if intent.audio is AudioChoice.REMOVE:
            return self._video_only_plan(intent, source_container)

        return self._full_video_plan(intent, source_container)

    def _selector(self, intent: OutputIntent, *, audio_only: bool) -> str:
        if audio_only:
            return "worstaudio" if intent.quality.value == "worst" else "bestaudio"
        return "worst" if intent.quality.value == "worst" else "bestvideo*+bestaudio/best"

    def _audio_plan(self, intent: OutputIntent) -> ExecutionPlan:
        codec = _AUDIO_CODEC_FOR_CONTAINER[intent.container]
        steps = (
            PlanStep(
                "SELECT_FORMAT", "yt_dlp", {"selector": self._selector(intent, audio_only=True)}
            ),
            PlanStep("DOWNLOAD", "yt_dlp", {}),
            PlanStep("EXTRACT_AUDIO", "ffmpeg", {"codec": codec, "container": intent.container}),
            PlanStep("VALIDATE", "ffprobe", {}),
            PlanStep("FINALIZE", "internal", {}),
        )
        return ExecutionPlan(steps=steps, strategy="extract_audio")

    def _video_only_plan(self, intent: OutputIntent, source_container: str | None) -> ExecutionPlan:
        compatible = source_container is not None and source_container in _CONTAINER_ACCEPTS.get(
            intent.container, frozenset()
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
            return ExecutionPlan(steps=steps, strategy="video_only")
        steps = (
            PlanStep(
                "SELECT_FORMAT", "yt_dlp", {"selector": self._selector(intent, audio_only=False)}
            ),
            PlanStep("DOWNLOAD", "yt_dlp", {}),
            PlanStep(
                "TRANSCODE",
                "ffmpeg",
                {
                    "video_codec": "libvpx-vp9" if intent.container == "webm" else "libx264",
                    "audio": "none",
                    "container": intent.container,
                },
            ),
            PlanStep("VALIDATE", "ffprobe", {}),
            PlanStep("FINALIZE", "internal", {}),
        )
        return ExecutionPlan(steps=steps, strategy="transcode")

    def _full_video_plan(self, intent: OutputIntent, source_container: str | None) -> ExecutionPlan:
        compatible = source_container is not None and source_container in _CONTAINER_ACCEPTS.get(
            intent.container, frozenset()
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
            return ExecutionPlan(steps=steps, strategy="copy")
        steps = (
            PlanStep(
                "SELECT_FORMAT", "yt_dlp", {"selector": self._selector(intent, audio_only=False)}
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
                },
            ),
            PlanStep("VALIDATE", "ffprobe", {}),
            PlanStep("FINALIZE", "internal", {}),
        )
        return ExecutionPlan(steps=steps, strategy="transcode")


def _primary_container(info: MediaInfo) -> str | None:
    """Best-effort source container from the resolved formats."""
    containers = [f.container or f.extension for f in info.formats]
    containers = [c.lower() for c in containers if c]
    if not containers:
        return None
    return max(set(containers), key=containers.count)

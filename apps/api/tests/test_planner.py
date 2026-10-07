"""Tests for the execution planner (Phase 5 acceptance)."""

from __future__ import annotations

import pytest

from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.intent import parse_intent
from local_media_downloader.domain.media import (
    FormatKind,
    MediaFormat,
    MediaInfo,
    MediaSource,
)
from local_media_downloader.services.planner import Planner


def _fmt(fmt_id: str, kind: FormatKind, container: str, extension: str) -> MediaFormat:
    return MediaFormat(
        id=fmt_id,
        kind=kind,
        container=container,
        extension=extension,
        video_codec="h264" if kind is not FormatKind.AUDIO else None,
        audio_codec="aac" if kind is not FormatKind.VIDEO else None,
        width=1920 if kind is not FormatKind.AUDIO else None,
        height=1080 if kind is not FormatKind.AUDIO else None,
        fps=30.0 if kind is not FormatKind.AUDIO else None,
        bitrate=None,
        audio_bitrate=None,
        filesize=None,
        filesize_approx=True,
        dynamic_range=None,
        protocol="https",
        has_video=kind is not FormatKind.AUDIO,
        has_audio=kind is not FormatKind.VIDEO,
        quality_score=0.0,
    )


def _info(*formats: MediaFormat) -> MediaInfo:
    return MediaInfo(
        source=MediaSource(
            url="https://example.com/v",
            extractor="generic",
            extractor_key="generic",
            title="t",
            uploader=None,
        ),
        id="v",
        duration_seconds=10.0,
        thumbnail_url=None,
        is_live=False,
        formats=tuple(formats),
    )


def _mp4_source() -> MediaInfo:
    return _info(_fmt("v", FormatKind.COMBINED, "mp4", "mp4"))


def _plan(intent_dict: dict[str, object], info: MediaInfo):
    return Planner().plan(parse_intent(intent_dict), info)


def test_stream_copy_is_preferred_when_compatible() -> None:
    plan = _plan(
        {
            "media": "video",
            "quality": "best",
            "container": "mp4",
            "audio": "include",
            "video_codec": "source",
        },
        _mp4_source(),
    )
    assert plan.strategy == "copy"
    kinds = [s.kind for s in plan.steps]
    assert "REMUX" in kinds
    assert "TRANSCODE" not in kinds


def test_transcode_only_when_container_incompatible() -> None:
    plan = _plan(
        {
            "media": "video",
            "quality": "best",
            "container": "webm",
            "audio": "include",
            "video_codec": "source",
        },
        _mp4_source(),
    )
    assert plan.strategy == "transcode"
    kinds = [s.kind for s in plan.steps]
    assert "TRANSCODE" in kinds
    assert "REMUX" not in kinds


def test_source_compatible_webm_copies() -> None:
    webm_source = _info(_fmt("v", FormatKind.COMBINED, "webm", "webm"))
    plan = _plan(
        {
            "media": "video",
            "quality": "best",
            "container": "webm",
            "audio": "include",
            "video_codec": "source",
        },
        webm_source,
    )
    assert plan.strategy == "copy"


def test_audio_mp3_extracts_audio() -> None:
    plan = _plan(
        {
            "media": "audio",
            "quality": "best",
            "container": "mp3",
            "audio": "only",
            "video_codec": "source",
        },
        _mp4_source(),
    )
    assert plan.strategy == "extract_audio"
    kinds = [s.kind for s in plan.steps]
    assert "EXTRACT_AUDIO" in kinds
    step = next(s for s in plan.steps if s.kind == "EXTRACT_AUDIO")
    assert step.detail["codec"] == "libmp3lame"


def test_remove_audio_stream_copy_when_compatible() -> None:
    plan = _plan(
        {
            "media": "video",
            "quality": "best",
            "container": "mp4",
            "audio": "remove",
            "video_codec": "source",
        },
        _mp4_source(),
    )
    assert plan.strategy == "video_only"
    step = next(s for s in plan.steps if s.kind == "VIDEO_ONLY")
    assert step.detail["mode"] == "stream_copy"


def test_rejects_video_with_audio_container() -> None:
    with pytest.raises(ExtractionError) as exc:
        _plan(
            {
                "media": "video",
                "quality": "best",
                "container": "mp3",
                "audio": "include",
                "video_codec": "source",
            },
            _mp4_source(),
        )
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_rejects_unknown_keys_instead_of_accepting_arbitrary_args() -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_intent(
            {
                "media": "video",
                "quality": "best",
                "container": "mp4",
                "audio": "include",
                "video_codec": "source",
                "ffmpeg_args": ["-i", "evil"],
            }
        )
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT
    assert "unknown intent keys" in exc.value.message


def test_rejects_resize_until_phase_14() -> None:
    with pytest.raises(ExtractionError) as exc:
        _plan(
            {
                "media": "video",
                "quality": "best",
                "container": "mp4",
                "audio": "include",
                "video_codec": "source",
                "processing": {"resize": "720p"},
            },
            _mp4_source(),
        )
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize(
    ("container", "target"),
    [("gif", "gif"), ("webp", "webp"), ("sticker", "webp"), ("mobile", "mp4")],
)
def test_media_preset_has_closed_conversion_plan(container: str, target: str) -> None:
    plan = _plan(
        {
            "media": "video",
            "quality": "best",
            "container": container,
            "audio": "include" if container == "mobile" else "remove",
            "video_codec": "source",
        },
        _mp4_source(),
    )
    assert plan.strategy == "transcode"
    step = next(s for s in plan.steps if s.kind == "CONVERT_PRESET")
    assert step.detail == {"preset": container, "container": target}


@pytest.mark.parametrize("container", ["gif", "webp", "sticker", "mobile"])
def test_media_presets_reject_incompatible_audio(container: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_intent(
            {
                "media": "video",
                "quality": "best",
                "container": container,
                "audio": "remove" if container == "mobile" else "include",
            }
        )
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_media_presets_require_video() -> None:
    with pytest.raises(ExtractionError) as exc:
        _plan(
            {"media": "video", "quality": "best", "container": "gif", "audio": "remove"},
            _info(_fmt("a", FormatKind.AUDIO, "m4a", "m4a")),
        )
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_plan_is_serializable_and_has_no_user_args() -> None:
    plan = _plan(
        {
            "media": "audio",
            "quality": "best",
            "container": "opus",
            "audio": "only",
            "video_codec": "source",
        },
        _mp4_source(),
    )
    payload = plan.as_dict()
    assert payload["strategy"] == "extract_audio"
    steps = payload["steps"]
    assert isinstance(steps, list)
    step = next(s for s in steps if isinstance(s, dict) and s.get("kind") == "EXTRACT_AUDIO")
    assert step["detail"]["codec"] == "libopus"

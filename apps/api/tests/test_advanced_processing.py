"""Phase 14 — advanced processing capability matrix for subtitles and metadata.

Capability matrix:
- subtitles: not supported yet → UNSUPPORTED_INTENT
- metadata: not supported yet → UNSUPPORTED_INTENT
"""

from __future__ import annotations

import pytest

from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.intent import parse_intent
from local_media_downloader.domain.media import FormatKind, MediaFormat, MediaInfo, MediaSource
from local_media_downloader.services.planner import Planner


def _fmt() -> MediaFormat:
    return MediaFormat(
        id="v",
        kind=FormatKind.COMBINED,
        container="mp4",
        extension="mp4",
        video_codec="h264",
        audio_codec="aac",
        width=1920,
        height=1080,
        fps=30.0,
        bitrate=None,
        audio_bitrate=None,
        filesize=None,
        filesize_approx=True,
        dynamic_range=None,
        protocol="https",
        has_video=True,
        has_audio=True,
        quality_score=0.0,
    )


def _info() -> MediaInfo:
    return MediaInfo(
        source=MediaSource(
            url="https://example.com/v",
            extractor="generic",
            extractor_key="generic",
            title="t",
            uploader=None,
        ),
        id="v",
        duration_seconds=60.0,
        thumbnail_url=None,
        is_live=False,
        formats=(_fmt(),),
    )


def _intent(**kwargs):
    payload = {
        "media": "video",
        "quality": "best",
        "container": "mp4",
        "audio": "include",
        "video_codec": "source",
    }
    payload.update(kwargs)
    return payload


def test_parse_intent_defaults_subtitles_metadata_false():
    intent = parse_intent(_intent())
    assert intent.subtitles is False
    assert intent.metadata is False
    assert intent.as_dict()["subtitles"] is False
    assert intent.as_dict()["metadata"] is False


def test_parse_intent_accepts_subtitles_flag():
    intent = parse_intent(_intent(subtitles=True))
    assert intent.subtitles is True


def test_parse_intent_accepts_metadata_flag():
    intent = parse_intent(_intent(metadata=True))
    assert intent.metadata is True


@pytest.mark.parametrize("value", ["true", 1, 0, None, []])
def test_parse_intent_rejects_non_boolean_subtitles(value):
    payload = _intent()
    payload["subtitles"] = value
    with pytest.raises(ExtractionError) as exc:
        parse_intent(payload)
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize("value", ["true", 1, 0, None, []])
def test_parse_intent_rejects_non_boolean_metadata(value):
    payload = _intent()
    payload["metadata"] = value
    with pytest.raises(ExtractionError) as exc:
        parse_intent(payload)
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_planner_rejects_subtitles():
    intent = parse_intent(_intent(subtitles=True))
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(intent, _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT
    assert "Subtitle extraction is not supported yet" in exc.value.message


def test_planner_rejects_metadata():
    intent = parse_intent(_intent(metadata=True))
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(intent, _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT
    assert "Metadata editing is not supported yet" in exc.value.message


def test_planner_accepts_normal_intent():
    intent = parse_intent(_intent())
    plan = Planner().plan(intent, _info())
    assert plan is not None

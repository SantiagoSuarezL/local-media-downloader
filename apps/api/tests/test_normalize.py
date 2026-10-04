"""Normalization from raw yt-dlp JSON into the domain model.

These tests never spawn yt-dlp: they pin the translation boundary so a yt-dlp
schema change shows up here instead of leaking into the domain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_media_downloader.adapters.normalize import normalize, normalize_format, quality_score
from local_media_downloader.domain.media import FormatKind

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def raw() -> dict:
    return json.loads((FIXTURES / "yt_dlp_video.json").read_text(encoding="utf-8"))


def test_source_metadata_is_normalized(raw: dict) -> None:
    info = normalize(raw, requested_url=URL)
    assert info.id == "dQw4w9WgXcQ"
    assert info.source.extractor == "youtube"
    assert info.source.title == "Example Video Title"
    assert info.source.uploader == "Example Channel"
    assert info.duration_seconds == 212.0
    assert info.is_live is False
    assert info.source.url == URL


def test_formats_are_sorted_by_quality_score(raw: dict) -> None:
    info = normalize(raw, requested_url=URL)
    scores = [f.quality_score for f in info.formats]
    assert scores == sorted(scores, reverse=True)


def test_storyboard_without_streams_is_dropped(raw: dict) -> None:
    info = normalize(raw, requested_url=URL)
    assert "sb0" not in [f.id for f in info.formats]


def test_format_kinds_are_classified(raw: dict) -> None:
    info = normalize(raw, requested_url=URL)
    kinds = {f.id: f.kind for f in info.formats}
    assert kinds["18"] is FormatKind.COMBINED
    assert kinds["137"] is FormatKind.VIDEO
    assert kinds["140"] is FormatKind.AUDIO


def test_absence_is_null_not_a_fake_value(raw: dict) -> None:
    info = normalize(raw, requested_url=URL)
    combined = next(f for f in info.formats if f.id == "18")
    assert combined.dynamic_range is None
    assert combined.width == 640
    video_only = next(f for f in info.formats if f.id == "137")
    assert video_only.has_audio is False
    assert video_only.audio_bitrate is None


def test_approximate_filesize_is_flagged(raw: dict) -> None:
    info = normalize(raw, requested_url=URL)
    approximate = next(f for f in info.formats if f.id == "251")
    exact = next(f for f in info.formats if f.id == "137")
    assert approximate.filesize is None
    assert approximate.filesize_approx is True
    assert exact.filesize == 120000000
    assert exact.filesize_approx is False


def test_higher_framerate_ranks_first_at_equal_resolution(raw: dict) -> None:
    """1080p60 beats 1080p30: the score expresses representation quality only."""
    info = normalize(raw, requested_url=URL)
    top = info.formats[0]
    assert top.id == "251"
    assert top.height == 1080
    assert top.fps == 60


def test_combined_beats_video_only_of_equal_quality() -> None:
    combined = quality_score(
        FormatKind.COMBINED, height=1080, fps=30, video_bitrate=4500, audio_bitrate=128
    )
    video_only = quality_score(
        FormatKind.VIDEO, height=1080, fps=30, video_bitrate=4500, audio_bitrate=None
    )
    assert combined > video_only


def test_resolution_outranks_format_convenience() -> None:
    """A 360p muxed file must not outrank a 1080p video-only stream."""
    combined_1080 = quality_score(
        FormatKind.COMBINED, height=1080, fps=30, video_bitrate=4500, audio_bitrate=128
    )
    video_1080 = quality_score(
        FormatKind.VIDEO, height=1080, fps=30, video_bitrate=4500, audio_bitrate=None
    )
    combined_360 = quality_score(
        FormatKind.COMBINED, height=360, fps=30, video_bitrate=900, audio_bitrate=96
    )
    # Convenience only decides near-ties at the same resolution.
    assert combined_1080 > video_1080
    assert video_1080 > combined_360


def test_score_cannot_invent_resolution() -> None:
    """A 720p source must never score like a 1080p one (principle #6)."""
    sd = quality_score(FormatKind.VIDEO, height=720, fps=30, video_bitrate=2000, audio_bitrate=None)
    hd = quality_score(
        FormatKind.VIDEO, height=1080, fps=30, video_bitrate=2000, audio_bitrate=None
    )
    assert sd < hd


def test_audio_only_ranks_below_any_video() -> None:
    audio = quality_score(
        FormatKind.AUDIO, height=None, fps=None, video_bitrate=None, audio_bitrate=320
    )
    video = quality_score(
        FormatKind.VIDEO, height=360, fps=30, video_bitrate=500, audio_bitrate=None
    )
    assert audio < video


def test_live_source_produces_a_warning() -> None:
    info = normalize({"id": "x", "is_live": True, "formats": []}, requested_url=URL)
    assert info.is_live is True
    assert any("live" in w.lower() for w in info.warnings)


def test_no_usable_formats_produces_a_warning() -> None:
    info = normalize({"id": "x", "formats": []}, requested_url=URL)
    assert info.formats == ()
    assert any("no usable formats" in w for w in info.warnings)


def test_normalize_tolerates_missing_optional_fields() -> None:
    info = normalize({}, requested_url=URL)
    assert info.duration_seconds is None
    assert info.thumbnail_url is None
    assert info.source.url == URL
    assert info.formats == ()


def test_normalize_skips_non_dict_formats(raw: dict) -> None:
    raw["formats"].append("not-a-dict")
    info = normalize(raw, requested_url=URL)
    assert all(f.id for f in info.formats)


def test_direct_media_link_keeps_its_format_and_is_flagged() -> None:
    """A direct .mp4 link reports no codecs; it must not be dropped silently."""
    info = normalize(
        {
            "id": "clip",
            "extractor": "generic",
            "formats": [{"format_id": "0", "ext": "mp4", "vcodec": "unknown", "acodec": "unknown"}],
        },
        requested_url="https://example.com/clip.mp4",
    )
    assert [f.id for f in info.formats] == ["0"]
    only = info.formats[0]
    assert only.kind is FormatKind.VIDEO
    # Honest about what is not known: no invented codec, no invented audio.
    assert only.video_codec is None
    assert only.has_audio is False
    assert any("confirmed by probing" in w for w in info.warnings)


def test_unknown_container_without_codecs_is_dropped() -> None:
    info = normalize(
        {
            "id": "x",
            "formats": [{"format_id": "0", "ext": "bin", "vcodec": "none", "acodec": "none"}],
        },
        requested_url="https://example.com/x.bin",
    )
    assert info.formats == ()


def test_normalize_format_returns_none_without_id() -> None:
    assert normalize_format({"vcodec": "vp9", "acodec": "none", "height": 720}) is None


def test_as_dict_is_json_serializable(raw: dict) -> None:
    info = normalize(raw, requested_url=URL)
    payload = info.as_dict()
    assert json.loads(json.dumps(payload))["source"]["extractor"] == "youtube"
    formats = payload["formats"]
    assert isinstance(formats, list)
    assert set(formats[0]) >= {"id", "kind", "height", "quality_score"}

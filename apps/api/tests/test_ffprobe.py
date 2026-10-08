"""Tests for the FFprobe adapter.

The parsing tests are offline and deterministic: they feed a recorded
ffprobe payload through ``parse_probe`` and check the normalized model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_media_downloader.adapters.ffprobe import parse_probe
from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.probe import StreamKind

_SAMPLE = {
    "streams": [
        {
            "index": 0,
            "codec_name": "h264",
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "avg_frame_rate": "30000/1001",
            "bit_rate": "4500000",
        },
        {
            "index": 1,
            "codec_name": "aac",
            "codec_type": "audio",
            "sample_rate": "48000",
            "channels": 2,
            "bit_rate": "192000",
        },
    ],
    "format": {
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": "12.345000",
        "size": "7340032",
        "bit_rate": "4750000",
    },
}


def test_parse_probe_normalizes_format_and_streams() -> None:
    probe = parse_probe(json.dumps(_SAMPLE), path=Path("clip.mp4"))
    assert probe.container == "mov,mp4,m4a,3gp,3g2,mj2"
    assert probe.duration_seconds == pytest.approx(12.345)
    assert probe.size_bytes == 7340032
    assert probe.bitrate == 4750000
    assert probe.has_video is True
    assert probe.has_audio is True
    video = probe.video_stream
    assert video is not None
    assert video.kind is StreamKind.VIDEO
    assert video.codec_name == "h264"
    assert video.width == 1920
    assert video.height == 1080
    assert video.fps == pytest.approx(29.970, rel=1e-3)
    audio = probe.audio_stream
    assert audio is not None
    assert audio.codec_name == "aac"
    assert audio.sample_rate == 48000
    assert audio.channels == 2


def test_parse_probe_tolerates_missing_bitrate_and_unknown_streams() -> None:
    payload = {
        "streams": [{"index": 0, "codec_type": "data", "codec_name": "bin_data"}],
        "format": {"format_name": "mp3", "duration": "3.0"},
    }
    probe = parse_probe(json.dumps(payload), path=Path("song.mp3"))
    assert probe.has_video is False
    assert probe.has_audio is False
    assert probe.streams[0].kind is StreamKind.OTHER
    assert probe.bitrate is None
    assert probe.size_bytes is None


def test_parse_probe_rejects_empty_output() -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_probe("   ", path=Path("x.mp4"))
    assert exc.value.code is ErrorCode.EXTRACTION_FAILED


def test_parse_probe_rejects_malformed_json() -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_probe("{not json", path=Path("x.mp4"))
    assert exc.value.code is ErrorCode.EXTRACTION_FAILED


def test_parse_probe_rejects_missing_format_block() -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_probe(json.dumps({"streams": []}), path=Path("x.mp4"))
    assert exc.value.code is ErrorCode.EXTRACTION_FAILED


def _webp_payload(width: object, height: object, coded_width: object) -> dict:
    return {
        "streams": [
            {
                "index": 0,
                "codec_name": "webp",
                "codec_type": "video",
                "width": width,
                "height": height,
                "coded_width": coded_width,
                "coded_height": coded_width,
            }
        ],
        "format": {"format_name": "webp", "size": "10412"},
    }


def test_parse_probe_prefers_coded_dims_when_container_reports_zero() -> None:
    """Older ffprobe builds report width/height 0 for animated WebP."""
    probe = parse_probe(json.dumps(_webp_payload(0, 0, 512)), path=Path("sticker.webp"))
    video = probe.video_stream
    assert video is not None
    assert (video.width, video.height) == (512, 512)


def test_parse_probe_maps_zero_dims_to_none() -> None:
    """0 is never a real dimension: absence is None, not a fake value."""
    probe = parse_probe(json.dumps(_webp_payload(0, 0, 0)), path=Path("sticker.webp"))
    video = probe.video_stream
    assert video is not None
    assert video.width is None
    assert video.height is None

"""Phase 14 — video encode options capability matrix.

Encode options is the fourth advanced-processing capability. Matrix:

| target                         | options      | strategy                              |
|--------------------------------|--------------|---------------------------------------|
| mp4/mkv/webm (audio included)  | codec/rate/fps | transcode with the requested encode |
| mp4/mkv/webm (audio removed)   | yes          | transcode, no audio                   |
| mp3/m4a/opus/wav               | no           | rejected (audio-only)                 |
| gif/webp/sticker/mobile        | no           | rejected before execution             |
| live source                    | no           | rejected before execution             |
| incompatible container         | no           | rejected (codec/container matrix)     |
| encode + trim/resize/crop      | yes          | one-pass transcode                    |
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from local_media_downloader.adapters.ffmpeg import FFmpegProcessor
from local_media_downloader.db import initialize
from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.intent import (
    parse_intent,
    parse_video_bitrate,
    parse_video_framerate,
)
from local_media_downloader.domain.media import FormatKind, MediaFormat, MediaInfo, MediaSource
from local_media_downloader.services.events import EventBus
from local_media_downloader.services.executor import DefaultExecutor
from local_media_downloader.services.planner import Planner

_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


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


def _info(*, live: bool = False) -> MediaInfo:
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
        is_live=live,
        formats=(_fmt(),),
    )


def _intent(
    container: str,
    audio: str,
    *,
    video_codec: str = "source",
    video_bitrate: str | None = None,
    video_framerate: str | None = None,
    processing: dict[str, str] | None = None,
    media: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "media": media if media is not None else ("audio" if audio == "only" else "video"),
        "quality": "best",
        "container": container,
        "audio": audio,
        "video_codec": video_codec,
        "processing": processing or {},
    }
    if video_bitrate is not None:
        payload["video_bitrate"] = video_bitrate
    if video_framerate is not None:
        payload["video_framerate"] = video_framerate
    return payload


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2500k", "2500k"),
        ("64k", "64k"),
        ("64000k", "64000k"),
        ("  2500k  ", "2500k"),
        ("2500K", "2500k"),
    ],
)
def test_parse_video_bitrate_accepts_closed_formats(value: str, expected: str) -> None:
    assert parse_video_bitrate(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "2500",
        "k",
        "63k",
        "64001k",
        "2500m",
        "2500kb",
        "2500; rm -rf /",
    ],
)
def test_parse_video_bitrate_rejects_everything_else(value: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_video_bitrate(value)
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30", "30"),
        ("29.97", "29.97"),
        ("120", "120"),
        ("60.00", "60.00"),
    ],
)
def test_parse_video_framerate_accepts_closed_formats(value: str, expected: str) -> None:
    assert parse_video_framerate(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0",
        "121",
        "29.999",
        "abc",
        "30; rm -rf /",
        "30,fps=30",
    ],
)
def test_parse_video_framerate_rejects_everything_else(value: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_video_framerate(value)
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize(
    "codec",
    ["source", "h264", "vp9", "av1"],
)
def test_parse_intent_accepts_known_codecs(codec: str) -> None:
    intent = parse_intent(_intent("mp4", "include", video_codec=codec))
    assert intent.video_codec == codec


def test_parse_intent_rejects_unknown_codec() -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_intent(_intent("mp4", "include", video_codec="prores"))
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_parse_intent_validates_bitrate_and_framerate_up_front() -> None:
    with pytest.raises(ExtractionError):
        parse_intent(_intent("mp4", "include", video_bitrate="2500"))
    with pytest.raises(ExtractionError):
        parse_intent(_intent("mp4", "include", video_framerate="0"))


def test_intent_as_dict_carries_encode_options() -> None:
    intent = parse_intent(
        _intent("mp4", "include", video_codec="vp9", video_bitrate="1500k", video_framerate="30")
    )
    assert intent.as_dict()["video_codec"] == "vp9"
    assert intent.as_dict()["video_bitrate"] == "1500k"
    assert intent.as_dict()["video_framerate"] == "30"


def test_codec_forces_transcode_even_when_copy_is_possible() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include", video_codec="h264")), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["video_codec"] == "libx264"


def test_av1_maps_to_svtav1_encoder() -> None:
    plan = Planner().plan(parse_intent(_intent("mkv", "include", video_codec="av1")), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["video_codec"] == "libsvtav1"


def test_bitrate_only_forces_transcode_with_default_codec() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include", video_bitrate="1500k")), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["video_codec"] == "libx264"
    assert detail["bitrate"] == "1500k"


def test_framerate_only_forces_transcode() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include", video_framerate="24")), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["framerate"] == "24"


def test_no_encode_options_keeps_stream_copy() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include")), _info())
    assert plan.strategy == "copy"


def test_webm_vp9_codec_is_compatible() -> None:
    plan = Planner().plan(parse_intent(_intent("webm", "include", video_codec="vp9")), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["video_codec"] == "libvpx-vp9"


@pytest.mark.parametrize(
    ("container", "codec"),
    [
        ("webm", "h264"),
        ("mp4", "vp9"),
    ],
)
def test_incompatible_codec_container_pairs_are_rejected(container: str, codec: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent(container, "include", video_codec=codec)), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_encode_options_rejected_for_live_sources() -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(
            parse_intent(_intent("mp4", "include", video_bitrate="1500k")), _info(live=True)
        )
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize(
    ("container", "audio"),
    [("gif", "remove"), ("webp", "remove"), ("sticker", "remove"), ("mobile", "include")],
)
def test_encode_options_rejected_for_media_presets(container: str, audio: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent(container, audio, video_bitrate="1500k")), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize("container", ["mp3", "m4a", "opus", "wav"])
def test_encode_options_rejected_for_audio_only(container: str) -> None:
    payload = _intent(container, "only", video_bitrate="1500k", media="audio")
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(payload), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_encode_options_combine_with_geometry_in_one_pass() -> None:
    plan = Planner().plan(
        parse_intent(
            _intent(
                "mp4",
                "include",
                video_codec="h264",
                video_bitrate="1500k",
                processing={"crop": "640x480", "resize": "720p", "trim": "00:10-00:20"},
            )
        ),
        _info(),
    )
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["crop"] == "640x480"
    assert detail["resize"] == "720p"
    assert detail["trim_start"] == "10.000"
    assert detail["bitrate"] == "1500k"
    assert detail["video_codec"] == "libx264"


class _EncodeRecordingProcessor:
    """MediaTool stub whose transcode carries the encode-options signature."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def transcode(
        self,
        source: Path,
        destination: Path,
        *,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        video_bitrate: str | None = None,
        video_framerate: str | None = None,
        audio_normalize: bool = False,
        timeout: float = 0.0,
    ) -> Path:
        self.calls.append(
            {
                "video_codec": video_codec,
                "audio_codec": audio_codec,
                "video_bitrate": video_bitrate,
                "video_framerate": video_framerate,
            }
        )
        return destination


class _LegacyTranscoder:
    """MediaTool stub with the Phase 4 transcode signature (no encode options)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def transcode(
        self,
        source: Path,
        destination: Path,
        *,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        timeout: float = 0.0,
    ) -> Path:
        self.calls.append({"video_codec": video_codec, "audio_codec": audio_codec})
        return destination


def _executor_with(tmp_path: Path, processor: object) -> DefaultExecutor:
    return DefaultExecutor(
        initialize(tmp_path / "app.db"),
        extractor=None,
        processor=processor,  # type: ignore[arg-type]
        data_dir=tmp_path,
        bus=EventBus(),
        download_sem=asyncio.Semaphore(1),
        encode_sem=asyncio.Semaphore(1),
    )


def test_executor_forwards_encode_options_to_transcode(tmp_path: Path) -> None:
    recorder = _EncodeRecordingProcessor()
    executor = _executor_with(tmp_path, recorder)
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = ("TRANSCODE", "ffmpeg", {"container": "mp4", "bitrate": "1500k", "framerate": "24"})
    executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert recorder.calls == [
        {
            "video_codec": "libx264",
            "audio_codec": "aac",
            "video_bitrate": "1500k",
            "video_framerate": "24",
        }
    ]


def test_executor_plain_transcode_still_works_for_legacy_processors(tmp_path: Path) -> None:
    legacy = _LegacyTranscoder()
    executor = _executor_with(tmp_path, legacy)
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = ("TRANSCODE", "ffmpeg", {"container": "mp4"})
    executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert legacy.calls == [{"video_codec": "libx264", "audio_codec": "aac"}]


def test_executor_rejects_encode_options_when_processor_lacks_capability(
    tmp_path: Path,
) -> None:
    legacy = _LegacyTranscoder()
    executor = _executor_with(tmp_path, legacy)
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = ("TRANSCODE", "ffmpeg", {"container": "mp4", "bitrate": "1500k"})
    with pytest.raises(ExtractionError) as exc:
        executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT
    assert legacy.calls == []


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("encode") / "source.mp4"
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=6:size=320x240:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=6",
            "-c:v",
            "libx264",
            "-g",
            "30",
            "-c:a",
            "aac",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"cannot generate fixture clip: {completed.stderr}")
    return out


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_transcode_with_bitrate_and_framerate(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.transcode(
        clip, tmp_path / "out.mp4", video_bitrate="400k", video_framerate="15"
    )
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert probe.video_stream.codec_name == "h264"
    assert probe.video_stream.fps is not None
    assert abs(probe.video_stream.fps - 15.0) < 1.0


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_transcode_with_av1_codec(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.transcode(clip, tmp_path / "out.mkv", video_codec="libsvtav1")
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert probe.video_stream.codec_name == "av1"


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_transcode_with_vp9_codec_in_webm(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.transcode(
        clip, tmp_path / "out.webm", video_codec="libvpx-vp9", audio_codec="libopus"
    )
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert probe.video_stream.codec_name == "vp9"
    assert probe.has_audio


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_framerate_applies_with_resize(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.resize(clip, tmp_path / "out.mp4", target="240p", video_framerate="15")
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert probe.video_stream.height == 240
    assert probe.video_stream.fps is not None
    assert abs(probe.video_stream.fps - 15.0) < 1.0


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_trimmed_transcode_carries_encode_options(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.transcode_trimmed(
        clip, tmp_path / "out.mp4", start=1.0, end=3.0, video_bitrate="400k", video_framerate="10"
    )
    probe = processor.validate(out)
    assert probe.duration_seconds is not None
    assert abs(probe.duration_seconds - 2.0) < 1.0
    assert probe.video_stream is not None
    assert probe.video_stream.fps is not None
    assert abs(probe.video_stream.fps - 10.0) < 1.0

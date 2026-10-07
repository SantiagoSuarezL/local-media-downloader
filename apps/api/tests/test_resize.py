"""Phase 14 — resize capability matrix.

Resize is the second advanced-processing capability. Matrix:

| target                         | resize | strategy                         |
|--------------------------------|--------|----------------------------------|
| mp4/mkv/webm (audio included)  | yes    | transcode with scale             |
| mp4/mkv/webm (audio removed)   | yes    | transcode, no audio              |
| mp3/m4a/opus/wav               | no     | rejected (audio-only)            |
| gif/webp/sticker/mobile        | no     | rejected before execution        |
| live source                    | no     | rejected before execution        |
| trim + resize                  | yes    | transcode with scale + trim      |
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from local_media_downloader.adapters.ffmpeg import FFmpegProcessor
from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.intent import parse_intent, parse_resize
from local_media_downloader.domain.media import FormatKind, MediaFormat, MediaInfo, MediaSource
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


def _info(duration: float | None = 60.0, *, live: bool = False) -> MediaInfo:
    return MediaInfo(
        source=MediaSource(
            url="https://example.com/v",
            extractor="generic",
            extractor_key="generic",
            title="t",
            uploader=None,
        ),
        id="v",
        duration_seconds=duration,
        thumbnail_url=None,
        is_live=live,
        formats=(_fmt(),),
    )


def _intent(
    container: str, audio: str, resize: str | None = "720p", trim: str | None = None
) -> dict[str, object]:
    processing: dict[str, str] = {}
    if resize is not None:
        processing["resize"] = resize
    if trim is not None:
        processing["trim"] = trim
    return {
        "media": "audio" if audio == "only" else "video",
        "quality": "best",
        "container": container,
        "audio": audio,
        "video_codec": "source",
        "processing": processing,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("720p", "720p"),
        ("1080p", "1080p"),
        ("1280x720", "1280x720"),
        ("1920x1080", "1920x1080"),
        ("480P", "480p"),
    ],
)
def test_parse_resize_accepts_closed_formats(value: str, expected: str) -> None:
    assert parse_resize(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "720",
        "1080",
        "720p1080",
        "1280*720",
        "1280X720",
        "720p; rm -rf /",
        "0x0",
        "99999x99999",
    ],
)
def test_parse_resize_rejects_everything_else(value: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_resize(value)
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_parse_intent_validates_resize_up_front() -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_intent(_intent("mp4", "include", resize="720"))
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_intent_dto_shape_is_unchanged_by_resize() -> None:
    intent = parse_intent(_intent("mp4", "include"))
    assert intent.processing.as_dict() == {"resize": "720p", "trim": None, "crop": None}


def test_resize_forces_transcode_even_when_copy_is_possible() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include")), _info())
    assert plan.strategy == "transcode"
    kinds = [s.kind for s in plan.steps]
    assert "TRANSCODE" in kinds and "REMUX" not in kinds
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["resize"] == "720p"


def test_resize_video_only_never_stream_copies() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "remove")), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["audio"] == "none"
    assert detail["resize"] == "720p"


def test_no_resize_keeps_stream_copy() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include", resize=None)), _info())
    assert plan.strategy == "copy"


@pytest.mark.parametrize(
    ("container", "audio"),
    [("gif", "remove"), ("webp", "remove"), ("sticker", "remove"), ("mobile", "include")],
)
def test_resize_rejected_for_media_presets(container: str, audio: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent(container, audio)), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_resize_rejected_for_live_sources() -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent("mp4", "include")), _info(live=True))
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize("container", ["mp3", "m4a", "opus", "wav"])
def test_resize_rejected_for_audio_only(container: str) -> None:
    payload = {
        "media": "audio",
        "quality": "best",
        "container": container,
        "audio": "only",
        "video_codec": "source",
        "processing": {"resize": "720p"},
    }
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(payload), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_resize_with_trim_combines_both() -> None:
    plan = Planner().plan(
        parse_intent(_intent("mp4", "include", resize="720p", trim="00:10-00:20")), _info()
    )
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["resize"] == "720p"
    assert detail["trim_start"] == "10.000"
    assert detail["trim_end"] == "20.000"


class _NoResizeProcessor:
    def transcode(self, source: Path, destination: Path, **_kw: object) -> Path:
        return destination


def test_executor_rejects_resize_when_processor_lacks_capability(tmp_path: Path) -> None:
    import asyncio

    from local_media_downloader.db import initialize
    from local_media_downloader.services.events import EventBus

    executor = DefaultExecutor(
        initialize(tmp_path / "app.db"),
        extractor=None,
        processor=_NoResizeProcessor(),  # type: ignore[arg-type]
        data_dir=tmp_path,
        bus=EventBus(),
        download_sem=asyncio.Semaphore(1),
        encode_sem=asyncio.Semaphore(1),
    )
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = (
        "TRANSCODE",
        "ffmpeg",
        {"container": "mp4", "resize": "720p"},
    )
    with pytest.raises(ExtractionError) as exc:
        executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("resize") / "source.mp4"
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=6:size=160x120:rate=10",
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
def test_resize_to_720p_produces_correct_height(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.resize(clip, tmp_path / "out.mp4", target="720p")
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert probe.video_stream.height == 720
    assert probe.has_video and probe.has_audio


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_resize_to_dimensions_fits_bbox_preserving_aspect(clip: Path, tmp_path: Path) -> None:
    # 1280x720 is a maximum bbox, not an exact deforming stretch: the 4:3
    # fixture (160x120) fits by height → 960x720.
    processor = FFmpegProcessor()
    out = processor.resize(clip, tmp_path / "out.mp4", target="1280x720")
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert probe.video_stream.width == 960
    assert probe.video_stream.height == 720


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_resize_without_audio(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.resize(clip, tmp_path / "out.mp4", target="720p", audio_codec="none")
    probe = processor.validate(out)
    assert probe.has_video and not probe.has_audio
    assert probe.video_stream is not None
    assert probe.video_stream.height == 720


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_trimmed_resize_applies_both_in_one_pass(clip: Path, tmp_path: Path) -> None:
    # Trim + resize must not lose either operation: single-pass scale of the
    # [1s, 3s) window to 720p height.
    processor = FFmpegProcessor()
    out = processor.transcode_trimmed(
        clip, tmp_path / "out.mp4", start=1.0, end=3.0, resize_target="720p"
    )
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert probe.video_stream.height == 720
    assert probe.duration_seconds is not None
    assert abs(probe.duration_seconds - 2.0) < 1.0

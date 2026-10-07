"""Phase 14 — trim capability matrix.

Trim is the first advanced-processing capability. Matrix:

| target                         | trim | strategy                         |
|--------------------------------|------|----------------------------------|
| mp4/mkv/webm (audio included)  | yes  | transcode (accurate cut)         |
| mp4/mkv/webm (audio removed)   | yes  | transcode, no audio              |
| mp3/m4a/opus/wav               | yes  | extract_audio with window        |
| gif/webp/sticker/mobile        | no   | rejected before execution        |
| live source                    | no   | rejected before execution        |
| resize                         | no   | still rejected                   |
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from local_media_downloader.adapters.ffmpeg import FFmpegProcessor
from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.intent import parse_intent, parse_trim
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


def _intent(container: str, audio: str, trim: str | None = "00:10-00:20") -> dict[str, object]:
    return {
        "media": "audio" if audio == "only" else "video",
        "quality": "best",
        "container": container,
        "audio": audio,
        "video_codec": "source",
        "processing": {"trim": trim},
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("00:10-00:20", (10.0, 20.0)),
        ("1:02:03-1:02:10.5", (3723.0, 3730.5)),
        ("5-12.25", (5.0, 12.25)),
        ("0:00-0:01", (0.0, 1.0)),
    ],
)
def test_parse_trim_accepts_closed_formats(value: str, expected: tuple[float, float]) -> None:
    assert parse_trim(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "10",
        "20-10",
        "10-10",
        "a-b",
        "00:10-00:20-00:30",
        "00:10; rm -rf /-00:20",
        "-5-10",
        "00:99-01:00",
        "0-100000",
    ],
)
def test_parse_trim_rejects_everything_else(value: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_trim(value)
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_parse_intent_validates_trim_up_front() -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_intent(_intent("mp4", "include", trim="20-10"))
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_intent_dto_shape_is_unchanged_by_trim() -> None:
    intent = parse_intent(_intent("mp4", "include"))
    assert intent.processing.as_dict() == {"resize": None, "trim": "00:10-00:20"}


def test_trim_forces_transcode_even_when_copy_is_possible() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include")), _info())
    assert plan.strategy == "transcode"
    kinds = [s.kind for s in plan.steps]
    assert "TRANSCODE" in kinds and "REMUX" not in kinds
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["trim_start"] == "10.000"
    assert detail["trim_end"] == "20.000"


def test_trim_video_only_never_stream_copies() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "remove")), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["audio"] == "none"
    assert detail["trim_start"] == "10.000"


def test_trim_audio_extraction_carries_window() -> None:
    plan = Planner().plan(parse_intent(_intent("mp3", "only")), _info())
    assert plan.strategy == "extract_audio"
    detail = next(s.detail for s in plan.steps if s.kind == "EXTRACT_AUDIO")
    assert (detail["trim_start"], detail["trim_end"]) == ("10.000", "20.000")


def test_no_trim_keeps_stream_copy() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include", trim=None)), _info())
    assert plan.strategy == "copy"


@pytest.mark.parametrize(
    ("container", "audio"),
    [("gif", "remove"), ("webp", "remove"), ("sticker", "remove"), ("mobile", "include")],
)
def test_trim_rejected_for_media_presets(container: str, audio: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent(container, audio)), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_trim_rejected_for_live_sources() -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent("mp4", "include")), _info(live=True))
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_trim_start_beyond_duration_is_rejected() -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent("mp4", "include", trim="01:30-01:40")), _info(60.0))
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_trim_with_unknown_duration_is_allowed() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include")), _info(None))
    assert plan.strategy == "transcode"


def test_resize_is_still_rejected() -> None:
    payload = _intent("mp4", "include", trim=None)
    payload["processing"] = {"resize": "720p"}
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(payload), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


class _NoTrimProcessor:
    def transcode(self, source: Path, destination: Path, **_kw: object) -> Path:
        return destination


def test_executor_rejects_trim_when_processor_lacks_capability(tmp_path: Path) -> None:
    import asyncio

    from local_media_downloader.db import initialize
    from local_media_downloader.services.events import EventBus

    executor = DefaultExecutor(
        initialize(tmp_path / "app.db"),
        extractor=None,
        processor=_NoTrimProcessor(),  # type: ignore[arg-type]
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
        {"container": "mp4", "trim_start": "1.000", "trim_end": "2.000"},
    )
    with pytest.raises(ExtractionError) as exc:
        executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("trim") / "source.mp4"
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
def test_transcode_trimmed_cuts_the_requested_window(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.transcode_trimmed(clip, tmp_path / "out.mp4", start=1.0, end=3.0)
    probe = processor.validate(out)
    assert probe.duration_seconds is not None
    assert probe.duration_seconds == pytest.approx(2.0, abs=0.5)
    assert probe.has_video and probe.has_audio


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_transcode_trimmed_without_audio(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.transcode_trimmed(
        clip, tmp_path / "out.mp4", start=2.0, end=4.0, audio_codec="none"
    )
    probe = processor.validate(out)
    assert probe.has_video and not probe.has_audio
    assert probe.duration_seconds == pytest.approx(2.0, abs=0.5)


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_extract_audio_trimmed_cuts_the_requested_window(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.extract_audio_trimmed(clip, tmp_path / "out.mp3", start=1.0, end=3.0)
    probe = processor.validate(out)
    assert probe.has_audio and not probe.has_video
    assert probe.duration_seconds == pytest.approx(2.0, abs=0.5)


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_trim_past_end_of_media_fails_validation(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    destination = tmp_path / "out.mp4"
    with pytest.raises(ExtractionError):
        processor.transcode_trimmed(clip, destination, start=50.0, end=60.0)
    assert not destination.exists()

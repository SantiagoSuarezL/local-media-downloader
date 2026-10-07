"""Phase 14 — crop capability matrix.

Crop is the third advanced-processing capability. Matrix:

| target                         | crop | strategy                                     |
|--------------------------------|------|----------------------------------------------|
| mp4/mkv/webm (audio included)  | yes  | transcode with crop filter                   |
| mp4/mkv/webm (audio removed)   | yes  | transcode, no audio                          |
| mp3/m4a/opus/wav               | no   | rejected (audio-only)                        |
| gif/webp/sticker/mobile        | no   | rejected before execution                    |
| live source                    | no   | rejected before execution                    |
| crop + resize                  | yes  | transcode with crop then scale (one pass)    |
| trim + crop                    | yes  | transcode with trim + crop (one pass)        |
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from local_media_downloader.adapters.ffmpeg import FFmpegProcessor
from local_media_downloader.domain.errors import ErrorCode, ExtractionError
from local_media_downloader.domain.intent import parse_crop, parse_intent
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
    crop: str | None = "640x480",
    resize: str | None = None,
    trim: str | None = None,
) -> dict[str, object]:
    processing: dict[str, str] = {}
    if crop is not None:
        processing["crop"] = crop
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
        ("640x480", "640x480"),
        ("1280x720", "1280x720"),
        ("640x480+100+50", "640x480+100+50"),
        ("  640x480  ", "640x480"),
        ("640X480", "640x480"),
        ("320x240+0+0", "320x240+0+0"),
    ],
)
def test_parse_crop_accepts_closed_formats(value: str, expected: str) -> None:
    assert parse_crop(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "640",
        "640x",
        "x480",
        "640*480",
        "640:480",
        "641x481",  # odd sides cannot be encoded as yuv420p
        "0x0",
        "1x1",
        "99999x99999",
        "640x480+100",  # offsets are a pair or nothing
        "640x480-10-10",  # negative origins would pad with black
        "640x480+10; rm -rf /",
        "640x480,scale=1280:720",
    ],
)
def test_parse_crop_rejects_everything_else(value: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_crop(value)
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_parse_intent_validates_crop_up_front() -> None:
    with pytest.raises(ExtractionError) as exc:
        parse_intent(_intent("mp4", "include", crop="640"))
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_intent_dto_carries_crop() -> None:
    intent = parse_intent(_intent("mp4", "include", crop="640x480+10+20"))
    assert intent.processing.as_dict() == {
        "resize": None,
        "trim": None,
        "crop": "640x480+10+20",
    }


def test_crop_forces_transcode_even_when_copy_is_possible() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include")), _info())
    assert plan.strategy == "transcode"
    kinds = [s.kind for s in plan.steps]
    assert "TRANSCODE" in kinds and "REMUX" not in kinds
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["crop"] == "640x480"


def test_crop_video_only_never_stream_copies() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "remove")), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["audio"] == "none"
    assert detail["crop"] == "640x480"


def test_no_crop_keeps_stream_copy() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include", crop=None)), _info())
    assert plan.strategy == "copy"


@pytest.mark.parametrize(
    ("container", "audio"),
    [("gif", "remove"), ("webp", "remove"), ("sticker", "remove"), ("mobile", "include")],
)
def test_crop_rejected_for_media_presets(container: str, audio: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent(container, audio)), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_crop_rejected_for_live_sources() -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent("mp4", "include")), _info(live=True))
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize("container", ["mp3", "m4a", "opus", "wav"])
def test_crop_rejected_for_audio_only(container: str) -> None:
    payload = {
        "media": "audio",
        "quality": "best",
        "container": container,
        "audio": "only",
        "video_codec": "source",
        "processing": {"crop": "640x480"},
    }
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(payload), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_crop_with_resize_combines_both() -> None:
    plan = Planner().plan(
        parse_intent(_intent("mp4", "include", crop="640x480", resize="720p")), _info()
    )
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["crop"] == "640x480"
    assert detail["resize"] == "720p"


def test_crop_with_trim_combines_both() -> None:
    plan = Planner().plan(
        parse_intent(_intent("mp4", "include", crop="640x480", trim="00:10-00:20")), _info()
    )
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["crop"] == "640x480"
    assert detail["trim_start"] == "10.000"
    assert detail["trim_end"] == "20.000"


class _NoCropProcessor:
    def resize(
        self, source: Path, destination: Path, *, target: str, **_kw: object
    ) -> Path:  # pragma: no cover — never reached
        raise AssertionError("resize must not be used by a crop-only operation")

    def transcode(self, source: Path, destination: Path, **_kw: object) -> Path:  # pragma: no cover
        raise AssertionError("transcode must not be used when crop is unsupported")


def test_executor_rejects_crop_when_processor_lacks_capability(tmp_path: Path) -> None:
    import asyncio

    from local_media_downloader.db import initialize
    from local_media_downloader.services.events import EventBus

    executor = DefaultExecutor(
        initialize(tmp_path / "app.db"),
        extractor=None,
        processor=_NoCropProcessor(),  # type: ignore[arg-type]
        data_dir=tmp_path,
        bus=EventBus(),
        download_sem=asyncio.Semaphore(1),
        encode_sem=asyncio.Semaphore(1),
    )
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = ("TRANSCODE", "ffmpeg", {"container": "mp4", "crop": "640x480"})
    with pytest.raises(ExtractionError) as exc:
        executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("crop") / "source.mp4"
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
def test_crop_produces_the_exact_box(clip: Path, tmp_path: Path) -> None:
    # A crop box is exact, not a bbox: 160x120 is produced literally, with no
    # rescaling to a similar aspect ratio.
    processor = FFmpegProcessor()
    out = processor.crop(clip, tmp_path / "out.mp4", box="160x120")
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert (probe.video_stream.width, probe.video_stream.height) == (160, 120)
    assert probe.has_video and probe.has_audio


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_crop_with_offset_selects_a_window(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.crop(clip, tmp_path / "out.mp4", box="160x120+80+60")
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert (probe.video_stream.width, probe.video_stream.height) == (160, 120)


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_crop_without_audio(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.crop(clip, tmp_path / "out.mp4", box="160x120", audio_codec="none")
    probe = processor.validate(out)
    assert probe.has_video and not probe.has_audio
    assert probe.video_stream is not None
    assert (probe.video_stream.width, probe.video_stream.height) == (160, 120)


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_crop_then_resize_in_one_pass(clip: Path, tmp_path: Path) -> None:
    # Crop first, then scale: the 320x240 source cropped to 160x120 and scaled
    # to a 720p bbox gives 960x720 (4:3 preserved) — both operations survive.
    processor = FFmpegProcessor()
    out = processor.crop(clip, tmp_path / "out.mp4", box="160x120", resize_target="1280x720")
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert (probe.video_stream.width, probe.video_stream.height) == (960, 720)


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_trimmed_crop_applies_both_in_one_pass(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.transcode_trimmed(
        clip, tmp_path / "out.mp4", start=1.0, end=3.0, crop_box="160x120"
    )
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert (probe.video_stream.width, probe.video_stream.height) == (160, 120)
    assert probe.duration_seconds is not None
    assert abs(probe.duration_seconds - 2.0) < 1.0


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_trimmed_crop_and_resize_apply_all_three(clip: Path, tmp_path: Path) -> None:
    processor = FFmpegProcessor()
    out = processor.transcode_trimmed(
        clip,
        tmp_path / "out.mp4",
        start=1.0,
        end=3.0,
        crop_box="160x120",
        resize_target="1280x720",
    )
    probe = processor.validate(out)
    assert probe.video_stream is not None
    assert (probe.video_stream.width, probe.video_stream.height) == (960, 720)
    assert probe.duration_seconds is not None
    assert abs(probe.duration_seconds - 2.0) < 1.0


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_crop_beyond_the_frame_fails_validation(clip: Path, tmp_path: Path) -> None:
    # The source is 320x240; a 640x480 box with that offset cannot be produced,
    # so the job must fail instead of shipping a silently padded file.
    processor = FFmpegProcessor()
    with pytest.raises(ExtractionError) as exc:
        processor.crop(clip, tmp_path / "out.mp4", box="640x480+160+120")
    assert exc.value.code is ErrorCode.EXTRACTION_FAILED
    assert not (tmp_path / "out.mp4").exists()

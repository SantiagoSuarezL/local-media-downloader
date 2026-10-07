"""Phase 14 — audio normalization capability matrix.

Audio normalization applies ffmpeg's loudnorm filter (EBU R128: I=-14 LUFS,
LRA=11, TP=-1.5 dBTP). loudnorm is a FILTER, never a stream copy, so the
feature forces a transcode on full-video output and cannot ride a REMUX.
Matrix:

| target                        | normalize | strategy                      |
|-------------------------------|-----------|-------------------------------|
| mp4/mkv/webm (audio included) | yes       | transcode (never REMUX copy)  |
| mp3/m4a/opus/wav              | yes       | extract_audio with loudnorm   |
| audio=remove (video only)     | no        | rejected before execution     |
| gif/webp/sticker/mobile       | no        | rejected before execution     |
| trim (and any other option)   | combine   | same single transcode pass    |
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
from local_media_downloader.domain.intent import parse_intent
from local_media_downloader.domain.media import FormatKind, MediaFormat, MediaInfo, MediaSource
from local_media_downloader.services.events import EventBus
from local_media_downloader.services.executor import DefaultExecutor
from local_media_downloader.services.planner import Planner

_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
_LOUNDNORM = "loudnorm=I=-14:LRA=11:TP=-1.5"


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


def _info(duration: float | None = 60.0) -> MediaInfo:
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
        is_live=False,
        formats=(_fmt(),),
    )


def _intent(
    container: str,
    audio: str,
    *,
    normalize: bool | None = None,
    trim: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "media": "audio" if audio == "only" else "video",
        "quality": "best",
        "container": container,
        "audio": audio,
        "video_codec": "source",
    }
    if normalize is not None:
        payload["audio_normalize"] = normalize
    if trim is not None:
        payload["processing"] = {"trim": trim}
    return payload


def test_parse_intent_defaults_audio_normalize_to_false() -> None:
    intent = parse_intent(_intent("mp4", "include"))
    assert intent.audio_normalize is False
    assert intent.as_dict()["audio_normalize"] is False


def test_parse_intent_accepts_audio_normalize_flag() -> None:
    intent = parse_intent(_intent("mp4", "include", normalize=True))
    assert intent.audio_normalize is True
    assert intent.as_dict()["audio_normalize"] is True


@pytest.mark.parametrize("value", ["true", 1, 0, None, []])
def test_parse_intent_rejects_non_boolean_audio_normalize(value: object) -> None:
    payload = _intent("mp4", "include")
    payload["audio_normalize"] = value
    with pytest.raises(ExtractionError) as exc:
        parse_intent(payload)
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


def test_normalization_forces_transcode_even_when_copy_is_possible() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include", normalize=True)), _info())
    assert plan.strategy == "transcode"
    kinds = [s.kind for s in plan.steps]
    assert "TRANSCODE" in kinds and "REMUX" not in kinds
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["audio_normalize"] == "True"


def test_no_normalization_keeps_stream_copy_and_has_no_dead_flag() -> None:
    plan = Planner().plan(parse_intent(_intent("mp4", "include")), _info())
    assert plan.strategy == "copy"
    remux = next(s.detail for s in plan.steps if s.kind == "REMUX")
    assert "audio_normalize" not in remux


def test_normalization_rides_the_incompatible_transcode_too() -> None:
    plan = Planner().plan(parse_intent(_intent("webm", "include", normalize=True)), _info())
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert detail["video_codec"] == "libvpx-vp9"
    assert detail["audio_codec"] == "libopus"
    assert detail["audio_normalize"] == "True"


def test_normalization_audio_extraction_carries_the_flag() -> None:
    plan = Planner().plan(parse_intent(_intent("mp3", "only", normalize=True)), _info())
    assert plan.strategy == "extract_audio"
    detail = next(s.detail for s in plan.steps if s.kind == "EXTRACT_AUDIO")
    assert detail["audio_normalize"] == "True"


def test_no_normalization_audio_extraction_carries_a_false_flag() -> None:
    plan = Planner().plan(parse_intent(_intent("mp3", "only")), _info())
    detail = next(s.detail for s in plan.steps if s.kind == "EXTRACT_AUDIO")
    assert detail["audio_normalize"] == "False"


def test_normalization_combines_with_trim_in_one_pass() -> None:
    plan = Planner().plan(
        parse_intent(_intent("mp4", "include", normalize=True, trim="00:10-00:20")),
        _info(),
    )
    assert plan.strategy == "transcode"
    detail = next(s.detail for s in plan.steps if s.kind == "TRANSCODE")
    assert (detail["trim_start"], detail["trim_end"]) == ("10.000", "20.000")
    assert detail["audio_normalize"] == "True"


def test_normalization_rejected_for_video_only_output() -> None:
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent("mp4", "remove", normalize=True)), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


@pytest.mark.parametrize("container", ["gif", "webp", "sticker", "mobile"])
def test_normalization_rejected_for_media_presets(container: str) -> None:
    audio = "remove" if container != "mobile" else "include"
    with pytest.raises(ExtractionError) as exc:
        Planner().plan(parse_intent(_intent(container, audio, normalize=True)), _info())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT


class _RecordingProcessor:
    """MediaTool stub recording the ``audio_normalize`` flag it was called with."""

    def __init__(self) -> None:
        self.normalize_calls: list[tuple[str, bool]] = []

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
        self.normalize_calls.append(("transcode", audio_normalize))
        return destination

    def extract_audio(
        self,
        source: Path,
        destination: Path,
        *,
        codec: str = "libmp3lame",
        bitrate: str = "192k",
        audio_normalize: bool = False,
        timeout: float = 0.0,
    ) -> Path:
        self.normalize_calls.append(("extract_audio", audio_normalize))
        return destination

    def validate(self, path: Path, *, timeout: float = 0.0) -> object:
        return object()


class _LegacyProcessor:
    """Phase 4 transcode signature (no encode options, no normalization)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def transcode(
        self,
        source: Path,
        destination: Path,
        *,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        timeout: float = 0.0,
    ) -> Path:
        self.calls.append(video_codec)
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


def test_executor_forwards_normalization_to_transcode(tmp_path: Path) -> None:
    recorder = _RecordingProcessor()
    executor = _executor_with(tmp_path, recorder)
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = ("TRANSCODE", "ffmpeg", {"container": "mp4", "audio_normalize": "True"})
    executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert recorder.normalize_calls == [("transcode", True)]


def test_executor_forwards_normalization_to_extract_audio(tmp_path: Path) -> None:
    recorder = _RecordingProcessor()
    executor = _executor_with(tmp_path, recorder)
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = ("EXTRACT_AUDIO", "ffmpeg", {"container": "mp3", "audio_normalize": "True"})
    executor._process(operation, source, tmp_path / "o.mp3", asyncio.Event())
    assert recorder.normalize_calls == [("extract_audio", True)]


def test_executor_rejects_normalization_when_processor_lacks_capability(tmp_path: Path) -> None:
    legacy = _LegacyProcessor()
    executor = _executor_with(tmp_path, legacy)
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = ("TRANSCODE", "ffmpeg", {"container": "mp4", "audio_normalize": "True"})
    with pytest.raises(ExtractionError) as exc:
        executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT
    assert legacy.calls == []


def test_executor_omits_normalization_kwarg_for_legacy_processors(tmp_path: Path) -> None:
    # The flag exists in the plan but normalization is not requested: a
    # Phase-4-signature processor must keep working, keyword omitted.
    legacy = _LegacyProcessor()
    executor = _executor_with(tmp_path, legacy)
    source = tmp_path / "s.mp4"
    source.write_bytes(b"x")
    operation = ("TRANSCODE", "ffmpeg", {"container": "mp4", "audio_normalize": "False"})
    executor._process(operation, source, tmp_path / "o.mp4", asyncio.Event())
    assert legacy.calls == ["libx264"]


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("norm") / "source.mp4"
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


class _ArgvRecorder(FFmpegProcessor):
    """FFmpegProcessor that records the operation argv before running it."""

    def __init__(self) -> None:
        super().__init__()
        self.batches: list[list[str]] = []

    def _run(
        self,
        source: Path,
        destination: Path,
        operation_args: list[str],
        *,
        timeout: float,
    ) -> Path:
        self.batches.append(list(operation_args))
        return super()._run(source, destination, operation_args, timeout=timeout)


def _has_loudnorm(args: list[str]) -> bool:
    return "-af" in args and args[args.index("-af") + 1] == _LOUNDNORM


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_loudnorm_reaches_transcode_argv(clip: Path, tmp_path: Path) -> None:
    recorder = _ArgvRecorder()
    out = recorder.transcode(clip, tmp_path / "out.mp4", audio_normalize=True)
    assert _has_loudnorm(recorder.batches[0])
    probe = recorder.validate(out)
    assert probe.has_video and probe.has_audio


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_transcode_without_normalization_has_no_audio_filter(clip: Path, tmp_path: Path) -> None:
    recorder = _ArgvRecorder()
    recorder.transcode(clip, tmp_path / "out.mp4")
    assert "-af" not in recorder.batches[0]


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_no_audio_filter_when_transcoding_without_audio(clip: Path, tmp_path: Path) -> None:
    # loudnorm against an audio-less output would make ffmpeg abort: the
    # audio_codec == "none" guard must win over a requested normalization.
    recorder = _ArgvRecorder()
    recorder.transcode(clip, tmp_path / "out.mp4", audio_codec="none", audio_normalize=True)
    args = recorder.batches[0]
    assert "-af" not in args
    assert "-an" in args


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_loudnorm_reaches_extract_audio_argv(clip: Path, tmp_path: Path) -> None:
    recorder = _ArgvRecorder()
    out = recorder.extract_audio(clip, tmp_path / "out.mp3", audio_normalize=True)
    assert _has_loudnorm(recorder.batches[0])
    probe = recorder.validate(out)
    assert probe.has_audio and not probe.has_video


@pytest.mark.skipif(not _FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_loudnorm_reaches_trimmed_resized_and_cropped_argv(clip: Path, tmp_path: Path) -> None:
    recorder = _ArgvRecorder()
    recorder.transcode_trimmed(clip, tmp_path / "t.mp4", start=1.0, end=3.0, audio_normalize=True)
    recorder.extract_audio_trimmed(
        clip, tmp_path / "t.mp3", start=1.0, end=3.0, audio_normalize=True
    )
    recorder.resize(clip, tmp_path / "r.mp4", target="240p", audio_normalize=True)
    recorder.crop(clip, tmp_path / "c.mp4", box="160x120", audio_normalize=True)
    for args in recorder.batches:
        assert _has_loudnorm(args)

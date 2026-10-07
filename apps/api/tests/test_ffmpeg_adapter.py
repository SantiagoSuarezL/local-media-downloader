"""Acceptance tests for Phase 4 FFmpeg/FFprobe adapters.

These run the real (offline) tools against a tiny synthetic clip generated
with lavfi sources. When ffmpeg/ffprobe are not installed the whole module
skips, so CI can stay deterministic on machines without the binaries.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from local_media_downloader.adapters.ffmpeg import FFmpegProcessor
from local_media_downloader.adapters.ffprobe import FFprobeInspector
from local_media_downloader.domain.errors import ErrorCode, ExtractionError

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


@pytest.fixture(scope="module")
def source_clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("media") / "source.mp4"
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=160x120:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
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


@pytest.fixture(scope="module")
def inspector() -> FFprobeInspector:
    return FFprobeInspector()


@pytest.fixture(scope="module")
def processor(inspector: FFprobeInspector) -> FFmpegProcessor:
    return FFmpegProcessor(inspector=inspector)


def test_probe_reports_video_and_audio(inspector: FFprobeInspector, source_clip: Path) -> None:
    probe = inspector.inspect(source_clip)
    assert probe.has_video is True
    assert probe.has_audio is True
    assert probe.duration_seconds is not None and probe.duration_seconds > 0
    video = probe.video_stream
    assert video is not None and video.width == 160 and video.height == 120


def test_mp4_can_be_produced(processor: FFmpegProcessor, source_clip: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    processor.transcode(source_clip, out)
    probe = processor.validate(out)
    assert probe.has_video is True
    assert probe.has_audio is True


def test_mp3_can_be_produced(processor: FFmpegProcessor, source_clip: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp3"
    processor.extract_audio(source_clip, out)
    probe = processor.validate(out)
    assert probe.has_audio is True
    assert probe.has_video is False


def test_audio_can_be_removed(
    processor: FFmpegProcessor, source_clip: Path, tmp_path: Path
) -> None:
    out = tmp_path / "video_only.mp4"
    processor.video_only(source_clip, out)
    probe = processor.validate(out)
    assert probe.has_video is True
    assert probe.has_audio is False


def test_remux_copies_streams(
    processor: FFmpegProcessor, source_clip: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out.mkv"
    processor.remux(source_clip, out)
    probe = processor.validate(out)
    assert probe.has_video is True
    assert probe.has_audio is True


@pytest.mark.parametrize(
    ("preset", "extension"),
    [("gif", "gif"), ("webp", "webp"), ("sticker", "webp"), ("mobile", "mp4")],
)
def test_preset_transforms_real_media(
    processor: FFmpegProcessor, source_clip: Path, tmp_path: Path, preset: str, extension: str
) -> None:
    out = tmp_path / f"{preset}.{extension}"
    processor.convert_preset(source_clip, out, preset=preset)
    probe = processor.validate(out)
    assert probe.has_video
    if preset != "mobile":
        assert not probe.has_audio
    if preset == "sticker":
        assert probe.video_stream is not None
        assert (probe.video_stream.width, probe.video_stream.height) == (512, 512)
        assert out.stat().st_size <= 500_000
    if preset == "mobile":
        assert probe.video_stream is not None
        assert probe.video_stream.height is not None and probe.video_stream.height <= 720


def test_missing_source_is_classified(processor: FFmpegProcessor, tmp_path: Path) -> None:
    with pytest.raises(ExtractionError) as exc:
        processor.transcode(tmp_path / "nope.mp4", tmp_path / "out.mp4")
    assert exc.value.code is ErrorCode.SOURCE_UNAVAILABLE


def test_validate_rejects_empty_file(processor: FFmpegProcessor, tmp_path: Path) -> None:
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(ExtractionError) as exc:
        processor.validate(empty)
    assert exc.value.code is ErrorCode.VALIDATION_FAILED


def test_validate_rejects_garbage_file(processor: FFmpegProcessor, tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.mp4"
    garbage.write_bytes(b"not a real media file" * 64)
    with pytest.raises(ExtractionError):
        processor.validate(garbage)

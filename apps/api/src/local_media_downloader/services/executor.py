"""Job executor: runs an ExecutionPlan against local tools.

The scheduler owns the durable state machine; the executor owns the actual
work for one job, publishing the normalized progress model and honoring the
cooperative cancel event. Every blocking tool call runs in a thread so the
asyncio loop stays responsive (one worker never stalls the others).

Concurrency budgets live in semaphores shared by the executor instance: at
most ``max_downloads`` yt-dlp downloads and at most ``max_encoders`` ffmpeg
processes run at once. An encoder slot is held only for the FFmpeg stages —
a downloading job never holds an encoder.
"""

from __future__ import annotations

import asyncio
import inspect
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, TypedDict, cast, runtime_checkable

from .. import jobs
from ..adapters.ffmpeg import FFmpegProcessor
from ..adapters.progress import DownloadProgress
from ..adapters.yt_dlp import YtDlpExtractor
from ..domain.errors import ErrorCode, ExtractionError
from ..domain.output import OutputRule, build_output_path
from ..domain.plan import ExecutionPlan
from ..domain.progress import JobProgress
from ..job_state import JobState
from .events import EventBus, StreamEvent


class JobCancelled(Exception):
    """Raised when the cooperative cancel event fires between stages."""


class _EncodeKwargs(TypedDict, total=False):
    video_bitrate: str | None
    video_framerate: str | None


def _encode_kwargs(detail: dict[str, str]) -> _EncodeKwargs:
    """Translate encode options from the plan into adapter kwargs.

    Only present keys are forwarded, so processors that predate these
    options (e.g. scheduler stubs) keep working when no encode options
    were requested.
    """
    kwargs: _EncodeKwargs = {}
    if detail.get("bitrate") is not None:
        kwargs["video_bitrate"] = detail["bitrate"]
    if detail.get("framerate") is not None:
        kwargs["video_framerate"] = detail["framerate"]
    return kwargs


def _supports_encode_options(processor: MediaTool) -> bool:
    """Prove the injected processor's ``transcode`` accepts the encode keywords.

    A ``runtime_checkable`` isinstance would only prove that a ``transcode``
    method exists — every ``MediaTool`` has one, Phase 4 stubs included, so
    the presence check cannot tell an extended processor from a legacy one.
    The capability lives in the keyword parameters, so those are inspected.
    """
    try:
        parameters = inspect.signature(processor.transcode).parameters
    except (TypeError, ValueError):  # pragma: no cover — callables without signatures
        return False
    return "video_bitrate" in parameters and "video_framerate" in parameters


class VideoEncodeOptionsTool(Protocol):
    """Optional capability: bitrate/framerate control (checked, never assumed).

    Deliberately not ``runtime_checkable``: it re-declares ``transcode``, a
    name every ``MediaTool`` already has, so a presence-based isinstance
    would match legacy processors too and prove nothing. The executor
    verifies the capability from the actual signature
    (``_supports_encode_options``) and only then calls through this type.
    """

    def transcode(
        self,
        source: Path,
        destination: Path,
        *,
        video_codec: str = ...,
        audio_codec: str = ...,
        video_bitrate: str | None = ...,
        video_framerate: str | None = ...,
        timeout: float = ...,
    ) -> Path: ...


class MediaTool(Protocol):
    """The slice of the FFmpeg adapter the executor needs (injectable for tests)."""

    def remux(self, source: Path, destination: Path, *, timeout: float = ...) -> Path: ...

    def transcode(
        self,
        source: Path,
        destination: Path,
        *,
        video_codec: str = ...,
        audio_codec: str = ...,
        timeout: float = ...,
    ) -> Path: ...

    def convert_preset(
        self, source: Path, destination: Path, *, preset: str, timeout: float = ...
    ) -> Path: ...

    def extract_audio(
        self,
        source: Path,
        destination: Path,
        *,
        codec: str = ...,
        bitrate: str = ...,
        timeout: float = ...,
    ) -> Path: ...

    def video_only(self, source: Path, destination: Path, *, timeout: float = ...) -> Path: ...

    def validate(self, path: Path, *, timeout: float = ...) -> object: ...


@runtime_checkable
class TrimTool(Protocol):
    """Optional capability: accurate time-window cuts (checked, never assumed)."""

    def transcode_trimmed(
        self,
        source: Path,
        destination: Path,
        *,
        start: float,
        end: float,
        video_codec: str = ...,
        audio_codec: str = ...,
        resize_target: str | None = ...,
        crop_box: str | None = ...,
        video_bitrate: str | None = ...,
        video_framerate: str | None = ...,
        timeout: float = ...,
    ) -> Path: ...

    def extract_audio_trimmed(
        self,
        source: Path,
        destination: Path,
        *,
        start: float,
        end: float,
        codec: str = ...,
        bitrate: str = ...,
        timeout: float = ...,
    ) -> Path: ...


@runtime_checkable
class ResizeTool(Protocol):
    """Optional capability: resolution scaling (checked, never assumed)."""

    def resize(
        self,
        source: Path,
        destination: Path,
        *,
        target: str,
        video_codec: str = ...,
        audio_codec: str = ...,
        video_bitrate: str | None = ...,
        video_framerate: str | None = ...,
        timeout: float = ...,
    ) -> Path: ...


@runtime_checkable
class CropTool(Protocol):
    """Optional capability: exact rectangle cropping (checked, never assumed)."""

    def crop(
        self,
        source: Path,
        destination: Path,
        *,
        box: str,
        resize_target: str | None = ...,
        video_codec: str = ...,
        audio_codec: str = ...,
        video_bitrate: str | None = ...,
        video_framerate: str | None = ...,
        timeout: float = ...,
    ) -> Path: ...


class Downloader(Protocol):
    """The slice of the yt-dlp adapter the executor needs (injectable for tests)."""

    def download(
        self,
        url: str,
        *,
        destination: Path,
        format_selector: str,
        timeout: float | None = None,
    ) -> Iterator[DownloadProgress]: ...


class DefaultExecutor:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        extractor: Downloader | None = None,
        processor: MediaTool | None = None,
        data_dir: Path,
        bus: EventBus,
        download_sem: asyncio.Semaphore,
        encode_sem: asyncio.Semaphore,
        output_root: Path | None = None,
        output_rule: OutputRule = OutputRule.FLAT,
    ) -> None:
        self._conn = conn
        self._extractor = extractor if extractor is not None else YtDlpExtractor()
        self._processor: MediaTool = processor if processor is not None else FFmpegProcessor()
        self._data_dir = data_dir
        self._bus = bus
        self._download_sem = download_sem
        self._encode_sem = encode_sem
        # Final media lives in the output root, not in the job directory: the job
        # directory holds temporary artifacts that retention may delete, while
        # the file the user asked for must survive that.
        self._output_root = output_root if output_root is not None else data_dir / "output"
        self._output_rule = output_rule

    async def run(
        self,
        job: jobs.Job,
        plan: ExecutionPlan,
        cancel: asyncio.Event,
    ) -> Path:
        job_dir = self._data_dir / "jobs" / job.id
        source_dir = job_dir / "source"
        work_dir = job_dir / "work"
        output_dir = job_dir / "output"
        for directory in (source_dir, work_dir, output_dir):
            directory.mkdir(parents=True, exist_ok=True)

        selector = _plan_detail(plan, "SELECT_FORMAT", "selector") or "best"
        url = job.source_url or ""
        self._loop = asyncio.get_running_loop()

        # --- download stage (yt-dlp), budgeted by the download semaphore ---
        async with self._download_sem:
            self._publish_state(job.id, JobState.DOWNLOADING, stage="download")
            try:
                await asyncio.to_thread(self._download, job, url, selector, source_dir, cancel)
            except Exception:
                raise
        _check_cancel(cancel)

        downloaded = _find_media_file(source_dir)
        if downloaded is None:
            raise ExtractionError(
                ErrorCode.EXTRACTION_FAILED,
                "The download produced no media file.",
                retryable=False,
            )

        # --- processing stage (ffmpeg), budgeted by the encoder semaphore ---
        operation = _first_operation(plan)
        work_file = downloaded
        if operation is not None:
            jobs.transition(self._conn, job.id, JobState.PROCESSING, current_stage="processing")
            self._publish_state(job.id, JobState.PROCESSING, stage="processing")
            container = operation[2].get("container", "mp4")
            target = work_dir / f"processed.{container}"
            async with self._encode_sem:
                await asyncio.to_thread(self._process, operation, downloaded, target, cancel)
            work_file = target
            _check_cancel(cancel)

        jobs.transition(self._conn, job.id, JobState.VALIDATING, current_stage="validating")
        self._publish_state(job.id, JobState.VALIDATING, stage="validating")
        await asyncio.to_thread(self._processor.validate, work_file)

        jobs.transition(self._conn, job.id, JobState.COMMITTING, current_stage="committing")
        container = _final_container(plan) or work_file.suffix.lstrip(".") or "bin"
        # The title comes from remote metadata, so it is sanitized and the
        # resulting path is proven to stay inside the output root.
        final = build_output_path(
            self._output_root,
            rule=self._output_rule,
            title=job.title,
            extension=container,
            extractor=job.extractor,
            created_at=job.created_at,
            fallback=job.id,
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(work_file), str(final))
        jobs.set_output_path(self._conn, job.id, str(final))
        return final

    def _download(
        self,
        job: jobs.Job,
        url: str,
        selector: str,
        source_dir: Path,
        cancel: asyncio.Event,
    ) -> None:
        for progress in self._extractor.download(
            url, destination=source_dir, format_selector=selector
        ):
            if cancel.is_set():
                raise JobCancelled()
            event = StreamEvent(
                kind="progress",
                job_id=job.id,
                payload={
                    "job_id": job.id,
                    **JobProgress(
                        state=JobState.DOWNLOADING.value,
                        stage="download",
                        percentage=progress.percentage,
                        downloaded_bytes=progress.downloaded_bytes,
                        total_bytes=progress.total_bytes,
                        speed_bytes_per_second=progress.speed_bytes_per_second,
                        eta_seconds=progress.eta_seconds,
                    ).as_dict(),
                },
            )
            # _download runs in a worker thread; the bus is asyncio-bound.
            self._loop.call_soon_threadsafe(self._bus.publish, event)

    def _process(
        self,
        operation: tuple[str, str, dict[str, str]],
        source: Path,
        target: Path,
        cancel: asyncio.Event,
    ) -> None:
        if cancel.is_set():
            raise JobCancelled()
        kind, _tool, detail = operation
        if "trim_start" in detail and kind in {"TRANSCODE", "EXTRACT_AUDIO"}:
            self._process_trimmed(kind, detail, source, target)
            return
        if kind == "TRANSCODE" and ("resize" in detail or "crop" in detail):
            self._process_geometry(detail, source, target)
            return
        if kind == "REMUX":
            self._processor.remux(source, target)
        elif kind == "TRANSCODE":
            encode_kwargs = _encode_kwargs(detail)
            if encode_kwargs and not _supports_encode_options(self._processor):
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "The media processor does not support encode options.",
                    retryable=False,
                )
            cast(VideoEncodeOptionsTool, self._processor).transcode(
                source,
                target,
                video_codec=detail.get("video_codec", "libx264"),
                audio_codec=detail.get(
                    "audio_codec", "none" if detail.get("audio") == "none" else "aac"
                ),
                **encode_kwargs,
            )
        elif kind == "CONVERT_PRESET":
            self._processor.convert_preset(source, target, preset=detail["preset"])
        elif kind == "EXTRACT_AUDIO":
            self._processor.extract_audio(source, target, codec=detail.get("codec", "libmp3lame"))
        elif kind == "VIDEO_ONLY":
            self._processor.video_only(source, target)
        else:  # pragma: no cover — guarded by _first_operation
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT, f"unknown processing step {kind}", retryable=False
            )

    def _process_trimmed(
        self, kind: str, detail: dict[str, str], source: Path, target: Path
    ) -> None:
        processor = self._processor
        if not isinstance(processor, TrimTool):
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "The media processor does not support trimming.",
                retryable=False,
            )
        start = float(detail["trim_start"])
        end = float(detail["trim_end"])
        if kind == "TRANSCODE":
            resize_target = detail.get("resize")
            crop_box = detail.get("crop")
            if resize_target is not None and not isinstance(processor, ResizeTool):
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "The media processor does not support resizing.",
                    retryable=False,
                )
            if crop_box is not None and not isinstance(processor, CropTool):
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "The media processor does not support cropping.",
                    retryable=False,
                )
            processor.transcode_trimmed(
                source,
                target,
                start=start,
                end=end,
                video_codec=detail.get("video_codec", "libx264"),
                audio_codec=detail.get(
                    "audio_codec", "none" if detail.get("audio") == "none" else "aac"
                ),
                resize_target=resize_target,
                crop_box=crop_box,
                **_encode_kwargs(detail),
            )
        else:
            if "resize" in detail or "crop" in detail:
                raise ExtractionError(
                    ErrorCode.UNSUPPORTED_INTENT,
                    "Resize and crop are not supported for audio-only output.",
                    retryable=False,
                )
            processor.extract_audio_trimmed(
                source, target, start=start, end=end, codec=detail.get("codec", "libmp3lame")
            )

    def _process_geometry(self, detail: dict[str, str], source: Path, target: Path) -> None:
        """Apply resize and/or crop in a single ffmpeg pass.

        Crop and resize are both pixel-geometry changes, so running them as two
        encodes would double the generation loss. The crop is expressed in
        source coordinates and is therefore applied first (see
        ``_video_filter_args`` in the adapter).
        """
        crop_box = detail.get("crop")
        resize_target = detail.get("resize")
        if crop_box is not None and resize_target is not None:
            self._process_cropped_and_resized(detail, crop_box, resize_target, source, target)
        elif crop_box is not None:
            self._process_cropped(
                detail, crop_box, resize_target=None, source=source, target=target
            )
        elif resize_target is not None:
            self._process_resized(detail, resize_target, source, target)

    def _process_cropped(
        self,
        detail: dict[str, str],
        crop_box: str,
        *,
        resize_target: str | None,
        source: Path,
        target: Path,
    ) -> None:
        processor = self._processor
        if not isinstance(processor, CropTool):
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "The media processor does not support cropping.",
                retryable=False,
            )
        processor.crop(
            source,
            target,
            box=crop_box,
            video_codec=detail.get("video_codec", "libx264"),
            audio_codec=detail.get(
                "audio_codec", "none" if detail.get("audio") == "none" else "aac"
            ),
            resize_target=resize_target,
            **_encode_kwargs(detail),
        )

    def _process_cropped_and_resized(
        self, detail: dict[str, str], crop_box: str, resize_target: str, source: Path, target: Path
    ) -> None:
        processor = self._processor
        if not isinstance(processor, CropTool) or not isinstance(processor, ResizeTool):
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "The media processor does not support cropping and resizing.",
                retryable=False,
            )
        processor.crop(
            source,
            target,
            box=crop_box,
            video_codec=detail.get("video_codec", "libx264"),
            audio_codec=detail.get(
                "audio_codec", "none" if detail.get("audio") == "none" else "aac"
            ),
            resize_target=resize_target,
            **_encode_kwargs(detail),
        )

    def _process_resized(
        self, detail: dict[str, str], resize_target: str, source: Path, target: Path
    ) -> None:
        processor = self._processor
        if not isinstance(processor, ResizeTool):
            raise ExtractionError(
                ErrorCode.UNSUPPORTED_INTENT,
                "The media processor does not support resizing.",
                retryable=False,
            )
        processor.resize(
            source,
            target,
            target=resize_target,
            video_codec=detail.get("video_codec", "libx264"),
            audio_codec=detail.get(
                "audio_codec", "none" if detail.get("audio") == "none" else "aac"
            ),
            **_encode_kwargs(detail),
        )

    def _publish_state(self, job_id: str, state: JobState, *, stage: str) -> None:
        self._bus.publish(
            StreamEvent(
                kind="state",
                job_id=job_id,
                payload={
                    "job_id": job_id,
                    **JobProgress(state=state.value, stage=stage).as_dict(),
                },
            )
        )


def _check_cancel(cancel: asyncio.Event) -> None:
    if cancel.is_set():
        raise JobCancelled()


def _plan_detail(plan: ExecutionPlan, kind: str, key: str) -> str | None:
    for step in plan.steps:
        if step.kind == kind:
            return step.detail.get(key)
    return None


def _first_operation(plan: ExecutionPlan) -> tuple[str, str, dict[str, str]] | None:
    for step in plan.steps:
        if step.kind in {"REMUX", "TRANSCODE", "EXTRACT_AUDIO", "VIDEO_ONLY", "CONVERT_PRESET"}:
            return step.kind, step.tool, dict(step.detail)
    return None


def _final_container(plan: ExecutionPlan) -> str | None:
    for step in plan.steps:
        if step.kind in {"REMUX", "TRANSCODE", "EXTRACT_AUDIO", "VIDEO_ONLY", "CONVERT_PRESET"}:
            container = step.detail.get("container")
            if container:
                return container
    return None


def _find_media_file(directory: Path) -> Path | None:
    candidates = sorted(
        p
        for p in directory.iterdir()
        if p.is_file()
        and p.suffix.lower()
        in {
            ".mp4",
            ".mkv",
            ".webm",
            ".mp3",
            ".m4a",
            ".opus",
            ".wav",
            ".mov",
            ".m4v",
            ".avi",
            ".flv",
            ".part",
        }
        and not p.name.endswith(".part")
    )
    return candidates[0] if candidates else None

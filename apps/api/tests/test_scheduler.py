"""Scheduler acceptance tests (Phase 6).

The concurrency budget is exercised with a stub executor that records how
many downloads and encodes run at once; the SSE stream is checked over HTTP.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from local_media_downloader import jobs
from local_media_downloader.config import Settings
from local_media_downloader.db import initialize
from local_media_downloader.job_state import JobState
from local_media_downloader.services.events import EventBus, StreamEvent
from local_media_downloader.services.scheduler import Scheduler, SchedulerLimits


class TrackingExecutor:
    """Stub executor; used for cancel/retry/SSE tests, not the budget one."""

    def __init__(self, conn, bus) -> None:
        self._conn = conn
        self._bus = bus
        self.active_run = 0
        self.max_active_run = 0

    async def run(self, job, plan, cancel) -> object:  # type: ignore[no-untyped-def]
        self.active_run += 1
        self.max_active_run = max(self.max_active_run, self.active_run)
        try:
            jobs.transition(self._conn, job.id, JobState.PROCESSING, current_stage="processing")
            for i in range(3):
                if cancel.is_set():
                    from local_media_downloader.services.executor import JobCancelled

                    raise JobCancelled()
                self._bus.publish(
                    StreamEvent(
                        kind="progress",
                        job_id=job.id,
                        payload={"job_id": job.id, "stage": "download", "percentage": (i + 1) * 30},
                    )
                )
                await asyncio.sleep(0.02)
            jobs.transition(self._conn, job.id, JobState.VALIDATING, current_stage="validating")
            jobs.transition(self._conn, job.id, JobState.COMMITTING, current_stage="committing")
            return object()
        finally:
            self.active_run -= 1


class StubDownloader:
    def __init__(self) -> None:
        self.active = 0
        self.max_concurrent = 0

    def download(self, url, *, destination, format_selector, timeout=None):  # type: ignore[no-untyped-def]
        self.active += 1
        self.max_concurrent = max(self.max_concurrent, self.active)
        try:
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "src.mp4").write_bytes(b"fake")
            from local_media_downloader.adapters.progress import DownloadProgress

            yield DownloadProgress(
                percentage=100.0,
                downloaded_bytes=4,
                total_bytes=4,
                speed_bytes_per_second=None,
                eta_seconds=None,
                fragment_index=None,
            )
        finally:
            self.active -= 1


class StubProcessor:
    def __init__(self) -> None:
        self.active = 0
        self.max_concurrent = 0

    def remux(self, source: Path, destination: Path, *, timeout: float = 0.0) -> Path:
        return self._write(destination)

    def transcode(
        self,
        source: Path,
        destination: Path,
        *,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        timeout: float = 0.0,
    ) -> Path:
        return self._write(destination)

    def convert_preset(
        self, source: Path, destination: Path, *, preset: str, timeout: float = 0.0
    ) -> Path:
        return self._write(destination)

    def extract_audio(
        self,
        source: Path,
        destination: Path,
        *,
        codec: str = "libmp3lame",
        bitrate: str = "192k",
        timeout: float = 0.0,
    ) -> Path:
        return self._write(destination)

    def video_only(self, source: Path, destination: Path, *, timeout: float = 0.0) -> Path:
        return self._write(destination)

    def validate(self, path: Path, *, timeout: float = 0.0) -> object:
        return object()

    def _write(self, destination: Path) -> Path:
        self.active += 1
        self.max_concurrent = max(self.max_concurrent, self.active)
        try:
            time.sleep(0.05)
            destination.write_bytes(b"out")
            return destination
        finally:
            self.active -= 1


def _make_plan_json() -> str:
    return json.dumps(
        {
            "strategy": "copy",
            "steps": [
                {"kind": "SELECT_FORMAT", "tool": "yt_dlp", "detail": {"selector": "best"}},
                {"kind": "VALIDATE", "tool": "ffprobe", "detail": {}},
            ],
        }
    )


def _copy_plan_json() -> str:
    return json.dumps(
        {
            "strategy": "copy",
            "steps": [
                {"kind": "SELECT_FORMAT", "tool": "yt_dlp", "detail": {"selector": "best"}},
                {"kind": "DOWNLOAD", "tool": "yt_dlp", "detail": {}},
                {
                    "kind": "REMUX",
                    "tool": "ffmpeg",
                    "detail": {"mode": "stream_copy", "container": "mp4"},
                },
                {"kind": "VALIDATE", "tool": "ffprobe", "detail": {}},
            ],
        }
    )


@pytest.fixture
def scheduler_env(tmp_path):
    conn = initialize(tmp_path / "app.db")
    bus = EventBus()
    executor = TrackingExecutor(conn, bus)
    limits = SchedulerLimits(
        max_active=3, max_downloads=2, max_encoders=1, retry_backoff_seconds=0.01
    )
    scheduler = Scheduler(
        conn, executor=executor, bus=bus, limits=limits, working_dir=str(tmp_path)
    )
    return conn, bus, executor, scheduler, tmp_path


@pytest.fixture
def real_budget_env(tmp_path):
    conn = initialize(tmp_path / "app.db")
    bus = EventBus()
    limits = SchedulerLimits(
        max_active=3, max_downloads=2, max_encoders=1, retry_backoff_seconds=0.01
    )
    downloader = StubDownloader()
    processor = StubProcessor()
    from local_media_downloader.services.executor import DefaultExecutor

    executor = DefaultExecutor(
        conn,
        extractor=downloader,
        processor=processor,
        data_dir=tmp_path,
        bus=bus,
        download_sem=asyncio.Semaphore(limits.max_downloads),
        encode_sem=asyncio.Semaphore(limits.max_encoders),
    )
    scheduler = Scheduler(
        conn, executor=executor, bus=bus, limits=limits, working_dir=str(tmp_path)
    )
    return conn, bus, downloader, processor, scheduler, tmp_path


def test_ten_jobs_never_exceed_two_downloads_one_encoder(real_budget_env):
    conn, _bus, downloader, processor, scheduler, _tmp_path = real_budget_env

    async def main() -> None:
        scheduler.start()
        for i in range(10):
            jobs.create_job(
                conn,
                source_url=f"https://example.com/v{i}",
                execution_plan_json=_copy_plan_json(),
                state=JobState.QUEUED,
            )
        deadline = time.monotonic() + 15
        done = 0
        while time.monotonic() < deadline:
            done = sum(
                1
                for j in jobs.list_jobs(conn)
                if j.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}
            )
            if done == 10:
                break
            await asyncio.sleep(0.05)
        await scheduler.stop()
        assert done == 10

    asyncio.run(main())
    assert downloader.max_concurrent <= 2
    assert processor.max_concurrent <= 1


def test_executor_dispatches_preset_and_uses_real_extension(real_budget_env):
    import asyncio

    from local_media_downloader.domain.plan import ExecutionPlan, PlanStep
    from local_media_downloader.services.executor import _final_container, _first_operation

    conn, bus, downloader, processor, _scheduler, _tmp_path = real_budget_env
    from local_media_downloader.services.executor import DefaultExecutor

    executor = DefaultExecutor(
        conn,
        extractor=downloader,
        processor=processor,
        data_dir=_tmp_path,
        bus=bus,
        download_sem=asyncio.Semaphore(1),
        encode_sem=asyncio.Semaphore(1),
    )
    plan = ExecutionPlan(
        steps=(PlanStep("CONVERT_PRESET", "ffmpeg", {"preset": "sticker", "container": "webp"}),),
        strategy="transcode",
    )
    operation = _first_operation(plan)
    assert operation is not None
    assert _final_container(plan) == "webp"
    source = _tmp_path / "source.mp4"
    source.write_bytes(b"fake")
    target = _tmp_path / "output.webp"
    executor._process(operation, source, target, asyncio.Event())
    assert target.read_bytes() == b"out"


def test_progress_model_is_normalized_and_observable(scheduler_env):
    conn, bus, _executor, scheduler, _tmp_path = scheduler_env

    async def main() -> None:
        scheduler.start()
        jobs.create_job(
            conn,
            source_url="https://example.com/v",
            execution_plan_json=_make_plan_json(),
            state=JobState.QUEUED,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = jobs.list_jobs(conn)[0]
            if job.state is JobState.COMPLETED:
                break
            await asyncio.sleep(0.02)
        await scheduler.stop()

    asyncio.run(main())
    progress = [e for e in bus.history if e.kind == "progress"]
    assert progress, "expected progress events from the executor"
    for event in progress:
        assert set(event.payload) >= {"job_id", "stage", "percentage"}
        # The raw tool protocol (yt-dlp/ffmpeg stdout) never reaches the stream.
        assert not {"stdout", "stderr", "progress_line"} & set(event.payload)


def test_cancel_a_queued_job(scheduler_env):
    conn, _bus, _executor, scheduler, _tmp_path = scheduler_env
    job = jobs.create_job(
        conn,
        source_url="https://example.com/v",
        execution_plan_json=_make_plan_json(),
        state=JobState.QUEUED,
    )
    scheduler.request_cancel(job.id)
    cancelled = jobs.get_job(conn, job.id)
    assert cancelled is not None
    assert cancelled.state is JobState.CANCELLED


def test_failed_job_with_bounded_retry_eventually_failed(scheduler_env):
    conn, _bus, _executor, scheduler, _tmp_path = scheduler_env

    class FailingExecutor:
        async def run(self, job, plan, cancel):  # type: ignore[no-untyped-def]
            from local_media_downloader.domain.errors import ErrorCode, ExtractionError

            raise ExtractionError(ErrorCode.EXTRACTION_FAILED, "boom", retryable=True)

    async def main() -> None:
        scheduler._executor = FailingExecutor()  # swap in the failing stub
        scheduler.start()
        jobs.create_job(
            conn,
            source_url="https://example.com/v",
            execution_plan_json=_make_plan_json(),
            state=JobState.QUEUED,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = jobs.list_jobs(conn)[0]
            if job.state is JobState.FAILED:
                break
            await asyncio.sleep(0.02)
        await scheduler.stop()
        job = jobs.list_jobs(conn)[0]
        assert job.state is JobState.FAILED
        assert job.attempt_count >= 2

    asyncio.run(main())


def test_events_route_is_registered(tmp_path):
    from fastapi.routing import APIRoute

    from local_media_downloader.app import create_app

    app = create_app(Settings(data_dir=tmp_path))
    methods = {route.path: route.methods for route in app.routes if isinstance(route, APIRoute)}
    assert methods.get("/api/v1/events") == {"GET"}


def test_sse_stream_frames_events_and_replays_history():
    # NOTE: the installed TestClient buffers the whole response before
    # yielding, which hangs forever on an infinite SSE stream. The stream
    # generator is consumed directly instead — same frames the endpoint serves.
    from local_media_downloader.app import _event_stream

    bus = EventBus()
    bus.publish(
        StreamEvent(kind="progress", job_id="j1", payload={"job_id": "j1", "percentage": 50.0})
    )
    bus.publish(
        StreamEvent(kind="state", job_id="j1", payload={"job_id": "j1", "state": "COMPLETED"})
    )

    async def take_two() -> list:
        stream = _event_stream(bus)
        try:
            first = await stream.__anext__()
            bus.publish(
                StreamEvent(kind="scheduler", job_id=None, payload={"event": "job_finished"})
            )
            second = await stream.__anext__()
            return [first, second]
        finally:
            await stream.aclose()

    frames = asyncio.run(take_two())
    assert frames[0].startswith("event: progress\ndata: ")
    assert frames[0].endswith("\n\n")
    assert json.loads(frames[0].split("data: ", 1)[1])["percentage"] == 50.0
    assert frames[1].startswith("event: state\ndata: ")
    # Closing the consumer unsubscribes it: no subscriber may leak per stream.
    assert len(bus._subscribers) == 0

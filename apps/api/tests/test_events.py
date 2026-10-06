"""Unit tests for the SSE event bus.

The bus is the UI's progress protocol (TECHNICAL_SPEC §3): normalized events
only. These tests pin the delivery contract — replay for late subscribers,
bounded history, and no backpressure from slow clients.
"""

from __future__ import annotations

import asyncio

from local_media_downloader.services.events import EventBus, StreamEvent


def _event(kind: str = "progress", job_id: str | None = "j1", **payload: object) -> StreamEvent:
    return StreamEvent(kind=kind, job_id=job_id, payload={"job_id": job_id, **payload})


def test_subscriber_receives_published_events() -> None:
    async def main() -> list[StreamEvent]:
        bus = EventBus()
        queue = bus.subscribe()
        try:
            bus.publish(_event(percentage=10.0))
            return [await asyncio.wait_for(queue.get(), timeout=1.0)]
        finally:
            bus.unsubscribe(queue)

    received = asyncio.run(main())
    assert len(received) == 1
    assert received[0].kind == "progress"
    assert received[0].payload["percentage"] == 10.0


def test_late_subscriber_gets_history_replay() -> None:
    bus = EventBus()
    bus.publish(_event(kind="state", state="QUEUED"))
    queue = bus.subscribe()
    try:
        replayed = [queue.get_nowait()]
    finally:
        bus.unsubscribe(queue)
    assert len(replayed) == 1
    assert replayed[0].kind == "state"


def test_history_is_bounded() -> None:
    bus = EventBus(history_limit=3)
    for i in range(10):
        bus.publish(_event(percentage=float(i)))
    assert len(bus.history) == 3
    assert bus.history[-1].payload["percentage"] == 9.0


def test_slow_subscriber_does_not_block_publish() -> None:
    bus = EventBus()
    queue = bus.subscribe(max_queue=1)
    try:
        queue.put_nowait(_event(percentage=1.0))  # fill the subscriber queue
        for i in range(10):
            bus.publish(_event(percentage=float(i)))  # must not raise or block
    finally:
        bus.unsubscribe(queue)


def test_unsubscribe_stops_delivery() -> None:
    async def main() -> bool:
        bus = EventBus()
        queue = bus.subscribe()
        bus.unsubscribe(queue)
        bus.publish(_event(percentage=99.0))
        try:
            await asyncio.wait_for(queue.get(), timeout=0.05)
            return False
        except TimeoutError:
            return True

    assert asyncio.run(main()) is True


def test_sse_frame_format() -> None:
    frame = _event(kind="progress", job_id="j1", percentage=42.5).as_sse()
    assert frame.startswith("event: progress\ndata: ")
    assert frame.endswith("\n\n")

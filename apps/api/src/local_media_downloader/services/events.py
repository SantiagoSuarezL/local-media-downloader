"""In-process event bus for SSE progress and scheduler events.

The SSE stream is the UI's primary progress protocol (TECHNICAL_SPEC §3):
normalized events only, never raw tool stdout. The bus keeps a bounded
history so a UI that connects late still sees the most recent state, and
publishes to every connected subscriber. Slow subscribers drop events
rather than applying backpressure to the scheduler — the job state in
SQLite remains the source of truth; the stream is a view, not the record.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any

_HISTORY_LIMIT = 256


@dataclass(frozen=True, slots=True)
class StreamEvent:
    kind: str  # "state" | "progress" | "scheduler" | "job"
    job_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)

    def as_sse(self) -> str:
        import json

        return f"event: {self.kind}\ndata: {json.dumps(self.payload, ensure_ascii=False)}\n\n"


class EventBus:
    def __init__(self, *, history_limit: int = _HISTORY_LIMIT) -> None:
        self._history: deque[StreamEvent] = deque(maxlen=history_limit)
        self._subscribers: set[asyncio.Queue[StreamEvent]] = set()

    def publish(self, event: StreamEvent) -> None:
        self._history.append(event)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # A stalled client must not stall the scheduler. Drop the
                # oldest pending event for that subscriber to recover.
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def subscribe(self, *, max_queue: int = 256) -> asyncio.Queue[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=max_queue)
        for event in self._history:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                break
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[StreamEvent]) -> None:
        self._subscribers.discard(queue)

    @property
    def history(self) -> list[StreamEvent]:
        return list(self._history)

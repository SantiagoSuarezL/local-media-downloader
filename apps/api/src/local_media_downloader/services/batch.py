"""Batch submission: many URLs in, many independent jobs out.

Each item goes through the same path as a single submit — validate intent,
resolve, plan, dedupe, enqueue — so a batch can never do anything a single
request could not. Items are independent: one bad URL reports its own error and
the rest of the batch proceeds (PRD Journey C).

Duplicate detection runs per item, so pasting the same URL twice in one batch
collapses to a single job instead of failing.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from .. import jobs
from ..domain.dedupe import dedupe_key
from ..domain.errors import ErrorCode, ExtractionError
from ..domain.extractor import Extractor
from ..domain.intent import parse_intent
from ..job_state import JobState
from .events import EventBus, StreamEvent
from .planner import Planner
from .rate_limit import RateLimiter
from .resolve import ResolveService

STATUS_CREATED = "created"
STATUS_DUPLICATE = "duplicate"
STATUS_ERROR = "error"


@dataclass(frozen=True, slots=True)
class BatchItem:
    url: str
    intent: dict[str, Any]
    title: str | None = None
    priority: int = 0


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    index: int
    status: str
    job: jobs.Job | None = None
    error_code: str | None = None
    error_message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"index": self.index, "status": self.status}
        if self.job is not None:
            payload["job"] = {
                "id": self.job.id,
                "state": self.job.state.value,
                "title": self.job.title,
                "priority": self.job.priority,
            }
        if self.error_code is not None:
            payload["error"] = {"code": self.error_code, "message": self.error_message}
        return payload


async def submit_batch(
    conn: sqlite3.Connection,
    *,
    items: list[BatchItem],
    extractor: Extractor,
    planner: Planner,
    resolve: ResolveService,
    limiter: RateLimiter,
    bus: EventBus,
    client: str = "ui",
) -> list[BatchItemResult]:
    """Submit every item, returning one result per item in input order."""
    results: list[BatchItemResult] = []
    for index, item in enumerate(items):
        results.append(
            await _submit_one(
                conn,
                index=index,
                item=item,
                extractor=extractor,
                planner=planner,
                resolve=resolve,
                limiter=limiter,
                client=client,
            )
        )
    bus.publish(
        StreamEvent(
            kind="scheduler",
            job_id=None,
            payload={
                "event": "batch_submitted",
                "created": sum(1 for r in results if r.status == STATUS_CREATED),
                "duplicates": sum(1 for r in results if r.status == STATUS_DUPLICATE),
                "errors": sum(1 for r in results if r.status == STATUS_ERROR),
            },
        )
    )
    return results


async def _submit_one(
    conn: sqlite3.Connection,
    *,
    index: int,
    item: BatchItem,
    extractor: Extractor,
    planner: Planner,
    resolve: ResolveService,
    limiter: RateLimiter,
    client: str,
) -> BatchItemResult:
    try:
        intent = parse_intent(item.intent)
    except ExtractionError as error:
        return BatchItemResult(
            index, STATUS_ERROR, error_code=error.code.value, error_message=error.message
        )

    allowed, _retry_after = await limiter.allow(client)
    if not allowed:
        return BatchItemResult(
            index,
            STATUS_ERROR,
            error_code=ErrorCode.RATE_LIMITED.value,
            error_message="Too many resolve requests; wait a moment before retrying.",
        )

    try:
        info = await asyncio.to_thread(resolve.resolve, item.url)
        plan = planner.plan(intent, info)
    except ExtractionError as error:
        return BatchItemResult(
            index, STATUS_ERROR, error_code=error.code.value, error_message=error.message
        )

    key = dedupe_key(item.url, item.intent)
    duplicate = jobs.find_duplicate(conn, key)
    if duplicate is not None:
        return BatchItemResult(index, STATUS_DUPLICATE, job=duplicate)

    job = jobs.create_job(
        conn,
        source_url=item.url,
        created_by=client,
        title=item.title or info.source.title,
        priority=item.priority,
        dedupe_key=key,
        intent_json=json.dumps(item.intent),
        execution_plan_json=json.dumps(plan.as_dict()),
        state=JobState.QUEUED,
    )
    return BatchItemResult(index, STATUS_CREATED, job=job)

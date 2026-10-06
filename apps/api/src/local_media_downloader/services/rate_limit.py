"""In-memory rate limiting for expensive endpoints.

Resolving a URL spawns yt-dlp (plus Deno) and can take seconds, so a stray
script or a mis-clicking tab could queue dozens of processes. The bucket is
per-client and in-process: there is one worker and no shared state to
coordinate, and the limiter disappears with the service, which is correct for a
loopback app.

A fixed window would allow a 2x burst across the boundary; a token bucket does
not, so the cost of a request is constant and predictable.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


class RateLimiter:
    def __init__(self, *, capacity: int, refill_per_second: float) -> None:
        if capacity < 1 or refill_per_second <= 0:
            raise ValueError("capacity must be >= 1 and refill_per_second > 0")
        self._capacity = float(capacity)
        self._refill = refill_per_second
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    def _refill_now(self, bucket: _Bucket, now: float) -> None:
        elapsed = max(now - bucket.updated_at, 0.0)
        bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill)
        bucket.updated_at = now

    async def allow(self, key: str) -> tuple[bool, float]:
        """Consume one token for ``key``.

        Returns ``(allowed, seconds_until_next_token)`` so the caller can tell
        the client when to retry instead of only that it failed.
        """
        async with self._lock:
            now = time.monotonic()
            bucket = self._buckets.get(key)
            if bucket is None:
                # A brand-new client starts full: the limit protects the service
                # from bursts, not the first legitimate request.
                bucket = _Bucket(tokens=self._capacity, updated_at=now)
                self._buckets[key] = bucket
            else:
                self._refill_now(bucket, now)
            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True, 0.0
            missing = 1 - bucket.tokens
            return False, missing / self._refill

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._buckets.clear()
        else:
            self._buckets.pop(key, None)


def per_minute_limiter(per_minute: int, *, burst: int | None = None) -> RateLimiter:
    """Build a limiter for an endpoint allowed ``per_minute`` calls per minute.

    ``burst`` defaults to ``per_minute``: the steady rate and the bucket size are
    the same number, which is the least surprising reading of "N per minute".
    """
    capacity = burst if burst is not None else per_minute
    return RateLimiter(capacity=capacity, refill_per_second=per_minute / 60.0)

"""Basic in-memory sliding-window rate limiter.

Per process, which is fine for the single backend replica this app runs as. With several
replicas it would move to Postgres or Redis (noted in docs/DECISIONS.md).
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self, clock=time.monotonic) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._clock = clock

    def check(self, key: str, limit: int, window_s: float) -> None:
        """Record a hit for `key`; raise 429 (with Retry-After) if it exceeds `limit` per window."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_s:
                hits.popleft()
            if len(hits) >= limit:
                retry = max(1, math.ceil(hits[0] + window_s - now))
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Rate limit reached. Try again in {_human(retry)}.",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def _human(seconds: int) -> str:
    if seconds < 90:
        return f"{seconds} s"
    return f"{math.ceil(seconds / 60)} min"


limiter = RateLimiter()

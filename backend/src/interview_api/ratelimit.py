"""Basic in-memory sliding-window rate limiter.

Per process, which is fine for the single backend replica this app runs as. With several
replicas it would move to Postgres or Redis (noted in docs/DECISIONS.md).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

MAX_WINDOW_S = 3600  # the longest window any caller uses; older hits are purged

log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, clock=time.monotonic, purge_every: int = 1000) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._clock = clock
        self._calls = 0
        self._purge_every = purge_every

    def _prune(self, key: str, window_s: float, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and hits[0] <= now - window_s:
            hits.popleft()
        return hits

    def _purge(self, now: float) -> None:
        """Drop keys with no hit inside the longest window, so memory stays bounded."""
        stale = [k for k, h in self._hits.items() if not h or h[-1] <= now - MAX_WINDOW_S]
        for k in stale:
            del self._hits[k]

    def _raise_if_full(
        self, key: str, hits: deque[float], limit: int, window_s: float, now: float
    ) -> None:
        if len(hits) >= limit:
            # Logged so per-IP keys can be checked behind a proxy; email keys are masked.
            scope, _, subject = key.partition(":")
            log.warning("rate limit hit: %s:%s", scope, "<email>" if "@" in subject else subject)
            retry = max(1, math.ceil(hits[0] + window_s - now))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit reached. Try again in {_human(retry)}.",
                headers={"Retry-After": str(retry)},
            )

    def ensure_below(self, key: str, limit: int, window_s: float) -> None:
        """Raise 429 if `key` is at its limit, without recording a hit."""
        now = self._clock()
        with self._lock:
            self._raise_if_full(key, self._prune(key, window_s, now), limit, window_s, now)

    def record(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            self._hits[key].append(now)
            self._calls += 1
            if self._calls % self._purge_every == 0:
                self._purge(now)

    def check(self, key: str, limit: int, window_s: float) -> None:
        """Record a hit for `key`; raise 429 (with Retry-After) if it exceeds `limit` per window."""
        self.ensure_below(key, limit, window_s)
        self.record(key)

    def __len__(self) -> int:
        return len(self._hits)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def _human(seconds: int) -> str:
    if seconds < 90:
        return f"{seconds} s"
    return f"{math.ceil(seconds / 60)} min"


limiter = RateLimiter()

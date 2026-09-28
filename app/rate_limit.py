# app/rate_limit.py
"""
Per-IP rate limiting for the public chat endpoint.

The widget on teep.africa makes POST /api/chat reachable by anyone, and every
allowed call spends an embedding plus a completion. This caps what a single
caller can spend without needing an account system.

Sliding window rather than fixed buckets: a fixed window lets someone send a
full allowance at 11:59:59 and another at 12:00:00, so the real burst is twice
the limit. The cost is keeping timestamps per caller, which is fine at support
volumes - see _sweep for how that is kept from growing without bound.

State lives in this process. Railway runs one replica by default, so that is
the whole service; if you scale to several, each gets its own allowance and the
effective limit multiplies by the replica count. Move to Redis or a Postgres
table at that point.
"""

import logging
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def resolve_client_ip(request: Request, trusted_hops: int = 1) -> str:
    """
    Best-effort caller identity from X-Forwarded-For.

    request.client.host is Railway's proxy, identical for every caller, so
    limiting on it would throttle all users as one. The proxy records the real
    address in X-Forwarded-For.

    Read from the right. A proxy *appends* the address it saw, so the rightmost
    entry is the one our nearest trusted proxy wrote and the only one it makes
    sense to trust - anything further left was supplied by the caller and can
    say whatever they like. Taking the leftmost value, which is the common
    mistake, would hand out a fresh allowance per forged header.

    trusted_hops says how many proxies sit in front of this app, so the value
    can be adjusted if Railway's topology changes, without touching this logic.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    parts = [p.strip() for p in forwarded.split(",") if p.strip()]
    if parts:
        index = max(0, len(parts) - max(1, trusted_hops))
        return parts[index]

    client = request.client
    return client.host if client else "unknown"


class SlidingWindowRateLimiter:
    """
    Enforces several windows at once, e.g. 6/minute and 40/hour.

    The short window keeps one person from hammering the widget; the long one
    stops a slow drip from quietly walking the whole knowledge base or running
    up the OpenAI bill overnight.
    """

    def __init__(self, limits: List[Tuple[int, int]], sweep_every: int = 300):
        # limits: (max_requests, window_seconds), stored longest window first so
        # _sweep can use limits[0] as the retention horizon.
        #
        # A non-positive allowance means "window off", so it is dropped here.
        # Kept as a filter rather than a guard in hit(): `count >= 0` is true on
        # the very first request, so leaving a zero in the list would reject
        # every call instead of disabling the window.
        usable = [(n, w) for n, w in limits if n > 0 and w > 0]
        self._limits = sorted(usable, key=lambda lim: lim[1], reverse=True)
        self._horizon = self._limits[0][1] if self._limits else 0
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()
        self._sweep_every = sweep_every
        self._last_sweep = time.monotonic()

    def _sweep(self, now: float) -> None:
        """
        Drop callers that have gone quiet.

        Without this the dict keeps one entry per address ever seen, which a
        stream of forged X-Forwarded-For values could grow until the process
        runs out of memory - turning a rate limiter into a way to take the
        service down. Called under the lock.
        """
        if now - self._last_sweep < self._sweep_every:
            return
        self._last_sweep = now
        cutoff = now - self._horizon
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= cutoff]:
            del self._hits[key]

    def hit(self, key: str) -> Optional[int]:
        """
        Record a request against `key`.

        Returns None when it is allowed, or the number of seconds to wait when
        it is not. A rejected request is deliberately not recorded: counting it
        would let a client hammering the endpoint keep pushing its own window
        forward and stay locked out indefinitely.
        """
        if not self._limits:
            return None

        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            hits = self._hits.get(key)
            if hits is None:
                hits = self._hits[key] = deque()

            # Everything older than the longest window is irrelevant to every
            # window, so one prune per call keeps each deque bounded.
            cutoff = now - self._horizon
            while hits and hits[0] <= cutoff:
                hits.popleft()

            for max_requests, window in self._limits:
                window_start = now - window
                # Timestamps ascend, so counting from the right stops as soon as
                # it leaves the window instead of walking the whole deque.
                count = 0
                for stamp in reversed(hits):
                    if stamp <= window_start:
                        break
                    count += 1
                if count >= max_requests:
                    oldest_in_window = hits[len(hits) - count]
                    return max(1, int(oldest_in_window + window - now) + 1)

            hits.append(now)
            return None


def build_dependency(
    limiter: SlidingWindowRateLimiter,
    trusted_hops: int = 1,
    message: str = "Too many requests. Please wait a moment and try again.",
):
    """
    Wrap a limiter as a FastAPI dependency.

    Raising from a dependency means a throttled request never reaches the
    embedding or completion call, so rejections cost nothing.
    """

    def dependency(request: Request) -> None:
        key = resolve_client_ip(request, trusted_hops)
        retry_after = limiter.hit(key)
        if retry_after is None:
            return
        logger.warning("Rate limited %s, retry after %ss", key, retry_after)
        raise HTTPException(
            status_code=429,
            # A plain string, not a list: the widget shows detail verbatim.
            detail=message,
            headers={"Retry-After": str(retry_after)},
        )

    return dependency

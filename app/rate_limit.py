# app/rate_limit.py
"""
Per-IP rate limiting for the public chat endpoint.

The widget on teep.africa makes POST /api/chat reachable by anyone, and every
allowed call spends an embedding plus a completion. This caps what a single
caller can spend without needing an account system.

Counters live in Postgres, not in the process. An in-process limiter was tried
first and measurably did not hold: Railway runs more than one replica, the load
balancer round-robins between them, and each kept its own tally - 24 requests
against a 6/minute limit let 13 through, with allowed and rejected calls
interleaved by which replica happened to answer. Shared state is what makes the
configured number the real number.

Sliding window rather than fixed buckets: a fixed window lets someone send a
full allowance at 11:59:59 and another at 12:00:00, so the real burst is twice
the limit.
"""

import logging
import threading
import time
from typing import List, Optional, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Hits are pruned to the longest window, so this table stays small: a few rows
# per active caller per hour. bucket_key is the caller identity, not a user id.
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rate_limit_hits (
    id BIGSERIAL PRIMARY KEY,
    bucket_key TEXT NOT NULL,
    hit_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS rate_limit_hits_key_time_idx
    ON rate_limit_hits (bucket_key, hit_at DESC);
CREATE INDEX IF NOT EXISTS rate_limit_hits_time_idx
    ON rate_limit_hits (hit_at);
"""


def ensure_schema(engine) -> None:
    """
    Create the counter table if it is missing.

    Called at startup so a deploy needs no migration step; scripts/db_reset.py
    creates the same table for a fresh database.
    """
    with engine.connect() as conn:
        conn.execute(text(_SCHEMA_SQL))
        conn.commit()


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


class PostgresRateLimiter:
    """
    Enforces several windows at once, e.g. 6/minute and 40/hour.

    The short window keeps one person from hammering the widget; the long one
    stops a slow drip from quietly walking the whole knowledge base or running
    up the OpenAI bill overnight.
    """

    def __init__(self, limits: List[Tuple[int, int]], cleanup_every: int = 300):
        # limits: (max_requests, window_seconds), longest window first so
        # limits[0] gives the retention horizon.
        #
        # A non-positive allowance means "window off", so it is dropped here.
        # Kept as a filter rather than a guard further down: `count >= 0` is
        # true on the very first request, so leaving a zero in the list would
        # reject every call instead of disabling the window.
        usable = [(n, w) for n, w in limits if n > 0 and w > 0]
        self._limits = sorted(usable, key=lambda lim: lim[1], reverse=True)
        self._horizon = self._limits[0][1] if self._limits else 0
        self._sql = text(self._build_sql()) if self._limits else None

        self._cleanup_every = cleanup_every
        self._cleanup_lock = threading.Lock()
        self._last_cleanup = 0.0

    def _build_sql(self) -> str:
        """
        One statement that counts, decides and records.

        Doing it in a single statement means every window is evaluated against
        the same snapshot, and the insert cannot land between the count and the
        decision. A data-modifying CTE always runs to completion in Postgres
        even when the outer query never selects from it, which is what lets the
        insert be conditional on `ok`.
        """
        counts, conditions, retries = [], [], []
        for i in range(len(self._limits)):
            in_window = "hit_at > now() - make_interval(secs => :w%d)" % i
            counts.append("count(*) FILTER (WHERE %s) AS n%d" % (in_window, i))
            counts.append("min(hit_at) FILTER (WHERE %s) AS o%d" % (in_window, i))
            conditions.append("n%d < :m%d" % (i, i))
            # Seconds until the oldest hit in this window ages out of it.
            retries.append(
                "COALESCE(CASE WHEN n{i} >= :m{i} THEN EXTRACT(EPOCH FROM "
                "(o{i} + make_interval(secs => :w{i}) - now())) END, 0)".format(i=i)
            )

        return """
            WITH win AS (
                SELECT {counts}
                FROM rate_limit_hits
                WHERE bucket_key = :key
                  AND hit_at > now() - make_interval(secs => :horizon)
            ),
            decision AS (
                SELECT *, ({conditions}) AS ok FROM win
            ),
            ins AS (
                INSERT INTO rate_limit_hits (bucket_key, hit_at)
                SELECT :key, now() FROM decision WHERE ok
                RETURNING 1
            )
            SELECT ok, GREATEST({retries}) AS retry_after FROM decision
        """.format(
            counts=", ".join(counts),
            conditions=" AND ".join(conditions),
            retries=", ".join(retries),
        )

    def _cleanup(self, db: Session) -> None:
        """
        Drop hits older than the longest window.

        Without this the table grows by one row per request forever. Forged
        X-Forwarded-For values make the key space unbounded too, so this is
        what stops a rate limiter from becoming a way to fill the disk.
        """
        now = time.monotonic()
        with self._cleanup_lock:
            if now - self._last_cleanup < self._cleanup_every:
                return
            self._last_cleanup = now
        deleted = db.execute(
            text(
                "DELETE FROM rate_limit_hits "
                "WHERE hit_at < now() - make_interval(secs => :horizon)"
            ),
            {"horizon": self._horizon},
        ).rowcount
        db.commit()
        if deleted:
            logger.info("Pruned %d expired rate-limit rows", deleted)

    def hit(self, db: Session, key: str) -> Optional[int]:
        """
        Record a request against `key`.

        Returns None when it is allowed, or the number of seconds to wait when
        it is not. A rejected request is deliberately not recorded: counting it
        would let a client hammering the endpoint keep pushing its own window
        forward and stay locked out indefinitely.
        """
        if not self._limits:
            return None

        params = {"key": key, "horizon": self._horizon}
        for i, (max_requests, window) in enumerate(self._limits):
            params["m%d" % i] = max_requests
            params["w%d" % i] = window

        # Serialise callers sharing a key. Without this two replicas can read
        # the same count concurrently and both admit the request; the lock is
        # per key, so unrelated callers never wait on each other. It is held
        # only until the commit below.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})

        row = db.execute(self._sql, params).one()
        db.commit()

        self._cleanup(db)

        if row.ok:
            return None
        return max(1, int(row.retry_after) + 1)


def build_dependency(
    limiter: PostgresRateLimiter,
    trusted_hops: int = 1,
    message: str = "Too many requests. Please wait a moment and try again.",
):
    """
    Wrap a limiter as a FastAPI dependency.

    Resolving from a dependency means a throttled request never reaches the
    embedding or completion call, so rejections cost nothing.
    """
    from app.db import get_db
    from fastapi import Depends

    def dependency(request: Request, db: Session = Depends(get_db)) -> None:
        key = resolve_client_ip(request, trusted_hops)
        try:
            retry_after = limiter.hit(db, key)
        except SQLAlchemyError:
            # Fail closed. The endpoint cannot answer without this same
            # database anyway, and failing open would leave spend uncapped
            # exactly when nobody is watching.
            db.rollback()
            logger.exception("Rate limiter could not reach Postgres")
            raise HTTPException(
                status_code=503,
                detail="The assistant is temporarily unavailable. Please try again shortly.",
            )

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

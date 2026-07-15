"""A small in-memory rate limiter for abuse-prone endpoints (hardening).

Keyed by client IP + a bucket name, using a sliding window. It's per-process and
in-memory — fine for the single-box deployment; it resets on restart and isn't
shared across workers. For a larger setup, swap this for a Redis-backed limiter
(e.g. slowapi).

Client IP: behind our Caddy reverse proxy the real client is the LAST hop of
X-Forwarded-For (Caddy appends it); locally there's no proxy so we fall back to
the socket peer. Taking the last hop avoids a client spoofing an earlier value.

Disable entirely with CIRQLE_RATE_LIMIT=off (used by the test suite).
"""
import os
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

# name -> ip -> deque[timestamps]
_hits: dict = defaultdict(lambda: defaultdict(deque))


def _enabled() -> bool:
    return os.environ.get("CIRQLE_RATE_LIMIT", "on").strip().lower() not in ("off", "0", "false", "no")


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, limit: int, window: int):
    """A FastAPI dependency allowing `limit` requests per `window` seconds per
    client IP for this `name` bucket. Raises 429 when exceeded."""
    def dep(request: Request) -> None:
        if not _enabled():
            return
        ip = _client_ip(request)
        now = time.monotonic()
        q = _hits[name][ip]
        cutoff = now - window
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait a moment and try again.",
            )
        q.append(now)
    return Depends(dep)

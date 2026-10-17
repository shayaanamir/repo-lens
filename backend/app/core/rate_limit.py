import math
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.core.config import settings


class SlidingWindowLimiter:
    """In-memory sliding-window counter. Resets on restart, which is fine
    for a free-tier demo; the hard backstops are the repo cap and AI budget."""

    def __init__(self, max_calls: int, window_seconds: float, clock=time.monotonic):
        self.max_calls = max_calls
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> float | None:
        """Records a hit. Returns None if allowed, otherwise the number of
        seconds until a slot frees up."""
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.max_calls:
            return self.window - (now - hits[0])
        hits.append(now)
        if len(self._hits) > 10_000:  # keep memory bounded
            self._hits = defaultdict(
                deque, {k: v for k, v in self._hits.items() if v}
            )
        return None


def rate_limit(max_calls: int, per_seconds: int, scope: str = "client"):
    """FastAPI dependency factory. Each call creates its own bucket, so
    every endpoint is limited independently. scope="global" shares one
    bucket across all clients."""
    limiter = SlidingWindowLimiter(max_calls, per_seconds)

    async def dependency(request: Request) -> None:
        if not settings.rate_limiting_enabled:
            return
        if scope == "global":
            key = "global"
        else:
            key = request.client.host if request.client else "unknown"
        retry_after = limiter.check(key)
        if retry_after is not None:
            seconds = math.ceil(retry_after)
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Please try again in {seconds}s.",
                headers={"Retry-After": str(seconds)},
            )

    return dependency
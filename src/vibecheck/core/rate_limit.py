"""Bounded in-memory IP rate limiter (OrderedDict LRU per python-backend skill)."""
from __future__ import annotations

import asyncio
import time
from collections import OrderedDict


class RateLimiter:
    """Sliding-window per-IP limiter. Bounded LRU to prevent memory blowup."""

    def __init__(self, max_per_window: int = 5, window_s: int = 60, max_ips: int = 5000) -> None:
        self.max_per_window = max_per_window
        self.window_s = window_s
        self.max_ips = max_ips
        self._hits: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def check(self, ip: str) -> bool:
        """Return True if allowed, False if over limit."""
        now = time.monotonic()
        cutoff = now - self.window_s
        async with self._lock:
            hits = self._hits.get(ip, [])
            hits = [t for t in hits if t > cutoff]
            if len(hits) >= self.max_per_window:
                self._hits[ip] = hits
                self._hits.move_to_end(ip)
                return False
            hits.append(now)
            self._hits[ip] = hits
            self._hits.move_to_end(ip)
            while len(self._hits) > self.max_ips:
                self._hits.popitem(last=False)
            return True

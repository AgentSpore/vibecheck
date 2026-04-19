"""In-memory TTL cache for shareable report URLs.

Stateless by design — no DB, no disk. On restart all share links expire.
This is intentional: reports contain personal inference data, shouldn't
persist long-term. 30 min TTL is enough to copy/paste a link in chat.
"""
from __future__ import annotations

import asyncio
import secrets
import time
import uuid
from typing import Any

_DEFAULT_TTL_S = 30 * 60  # 30 minutes
_MAX_ENTRIES = 1000  # hard cap to prevent memory abuse


class ShareCache:
    """Thread-safe in-memory cache with TTL + LRU-ish eviction."""

    def __init__(self, ttl_s: int = _DEFAULT_TTL_S, max_entries: int = _MAX_ENTRIES) -> None:
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def new_id() -> str:
        # uuid4 hex[:12] is ~48 bits of entropy — plenty for 30min-lived IDs.
        return uuid.uuid4().hex[:12]

    async def put(self, payload: dict[str, Any]) -> str:
        async with self._lock:
            self._evict_expired_locked()
            # If we're still over cap, drop oldest entry.
            if len(self._store) >= self._max_entries:
                oldest = min(self._store.items(), key=lambda kv: kv[1][0])[0]
                self._store.pop(oldest, None)
            share_id = self.new_id()
            # Collision is astronomically unlikely, but handle it.
            while share_id in self._store:
                share_id = secrets.token_hex(6)
            self._store[share_id] = (time.monotonic(), payload)
            return share_id

    async def get(self, share_id: str) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._store.get(share_id)
            if entry is None:
                return None
            created_at, payload = entry
            if time.monotonic() - created_at > self._ttl_s:
                self._store.pop(share_id, None)
                return None
            return payload

    def _evict_expired_locked(self) -> None:
        now = time.monotonic()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl_s]
        for k in expired:
            self._store.pop(k, None)


_cache_singleton: ShareCache | None = None


def get_share_cache() -> ShareCache:
    global _cache_singleton
    if _cache_singleton is None:
        _cache_singleton = ShareCache()
    return _cache_singleton

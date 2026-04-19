"""ShareCache TTL + eviction tests."""
from __future__ import annotations

import pytest

from vibecheck.core.share_cache import ShareCache


@pytest.mark.asyncio
async def test_put_get_roundtrip() -> None:
    cache = ShareCache(ttl_s=60)
    sid = await cache.put({"report": {"vibe_score": 80}})
    assert len(sid) == 12
    got = await cache.get(sid)
    assert got == {"report": {"vibe_score": 80}}


@pytest.mark.asyncio
async def test_missing_id_returns_none() -> None:
    cache = ShareCache()
    assert await cache.get("doesnotexist") is None


@pytest.mark.asyncio
async def test_expiry() -> None:
    cache = ShareCache(ttl_s=0)  # instant expiry
    sid = await cache.put({"x": 1})
    assert await cache.get(sid) is None


@pytest.mark.asyncio
async def test_max_entries_evicts_oldest() -> None:
    cache = ShareCache(ttl_s=3600, max_entries=3)
    ids = [await cache.put({"n": i}) for i in range(3)]
    # adding 4th should evict one
    await cache.put({"n": 99})
    alive = [await cache.get(sid) for sid in ids]
    assert alive.count(None) >= 1  # at least one evicted

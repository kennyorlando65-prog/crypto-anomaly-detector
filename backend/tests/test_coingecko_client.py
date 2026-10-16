"""Tests for the CoinGecko client's rate limiting and caching.

These run without network access. The point is to prove the client paces
itself and caches, because those two behaviours are what keep the app inside
the free tier.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from engine.coingecko import RateLimiter, TTLCache


@pytest.mark.asyncio
async def test_rate_limiter_allows_burst_up_to_capacity():
    """A fresh limiter must allow its full capacity immediately."""
    limiter = RateLimiter(calls_per_minute=5)
    start = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    assert time.monotonic() - start < 0.5


@pytest.mark.asyncio
async def test_rate_limiter_paces_beyond_capacity():
    """The sixth call must wait, because the bucket is empty."""
    limiter = RateLimiter(calls_per_minute=60)  # one token per second
    for _ in range(60):
        await limiter.acquire()
    start = time.monotonic()
    await limiter.acquire()
    assert time.monotonic() - start >= 0.5


@pytest.mark.asyncio
async def test_rate_limiter_serialises_concurrent_callers():
    """Concurrent callers must not all pass at once.

    This is the real-world case: a cold refresh of N assets fires N coroutines
    at the same moment. Without the lock they would all slip through.
    """
    limiter = RateLimiter(calls_per_minute=60)
    for _ in range(60):
        await limiter.acquire()

    start = time.monotonic()
    await asyncio.gather(*(limiter.acquire() for _ in range(3)))
    assert time.monotonic() - start >= 1.0


def test_cache_returns_stored_value():
    """A stored value must come back before it expires."""
    cache = TTLCache()
    cache.set("k", {"v": 1}, ttl=60)
    assert cache.get("k") == {"v": 1}


def test_cache_expires_entries():
    """An expired entry must be gone, not stale."""
    cache = TTLCache()
    cache.set("k", "v", ttl=0)
    time.sleep(0.01)
    assert cache.get("k") is None


def test_cache_miss_returns_none():
    """An unknown key must return None rather than raising."""
    assert TTLCache().get("absent") is None


def test_cache_stats_report_live_entries():
    """The health endpoint reports these numbers, so they must be right."""
    cache = TTLCache()
    cache.set("a", 1, ttl=60)
    cache.set("b", 2, ttl=0)
    time.sleep(0.01)
    stats = cache.stats()
    assert stats["entries"] == 2
    assert stats["live"] == 1


def test_cache_clear_empties_the_store():
    """Clearing must leave nothing behind."""
    cache = TTLCache()
    cache.set("a", 1, ttl=60)
    cache.clear()
    assert cache.stats()["entries"] == 0

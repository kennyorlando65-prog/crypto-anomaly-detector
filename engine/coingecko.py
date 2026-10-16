"""CoinGecko public API client.

Uses the keyless public API only. No API key, no signup, no paid tier.

RATE LIMITS (the honest numbers)
--------------------------------
CoinGecko's own knowledge base states the keyless public API allows roughly
5 to 15 calls per minute, varying with global load. Third-party write-ups
quote 10 to 50. The conservative figure is used here, because being throttled
is worse than being slow.

Two things keep this client inside the budget:

1. A token-bucket limiter that spaces requests out rather than firing them
   all at once.
2. A TTL cache, so a page refresh does not become an API call.

PAGINATION
----------
``/coins/markets`` returns up to 250 coins per page, so the market list costs
one call no matter how many assets are tracked. The per-asset history
endpoint is the expensive one: one call per asset per refresh.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Conservative keyless limit. See module docstring.
DEFAULT_CALLS_PER_MINUTE = 10

# How long a cached response stays fresh, in seconds.
MARKET_CACHE_TTL = 120
HISTORY_CACHE_TTL = 900


class RateLimiter:
    """A simple token bucket, refilled at a fixed rate.

    ``acquire`` waits until a token is available, so callers never need to
    think about pacing. This is what stops a cold refresh of N assets from
    firing N requests in the same second and getting a 429.
    """

    def __init__(self, calls_per_minute: int = DEFAULT_CALLS_PER_MINUTE) -> None:
        self.capacity = max(1, calls_per_minute)
        self.tokens = float(self.capacity)
        self.refill_rate = self.capacity / 60.0  # tokens per second
        self.updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.updated_at
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                self.updated_at = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                deficit = 1.0 - self.tokens
                await asyncio.sleep(deficit / self.refill_rate)


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """A tiny in-process cache with per-entry expiry.

    Deliberately not Redis. The free tier has no Redis, and a single
    serverless instance does not need one. The trade-off is that each warm
    instance keeps its own cache, which is documented in the README.
    """

    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = _CacheEntry(value=value, expires_at=time.monotonic() + ttl)

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> dict:
        now = time.monotonic()
        live = sum(1 for e in self._store.values() if e.expires_at >= now)
        return {"entries": len(self._store), "live": live}


class CoinGeckoError(RuntimeError):
    """Raised when CoinGecko cannot be reached or returns an error."""


class CoinGeckoClient:
    """Async client for the endpoints this project needs."""

    def __init__(
        self,
        calls_per_minute: int = DEFAULT_CALLS_PER_MINUTE,
        timeout: float = 20.0,
    ) -> None:
        self.limiter = RateLimiter(calls_per_minute)
        self.cache = TTLCache()
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> CoinGeckoClient:
        self._client = httpx.AsyncClient(
            base_url=COINGECKO_BASE,
            timeout=self.timeout,
            headers={"accept": "application/json", "user-agent": "crypto-anomaly-detector"},
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict | None = None, retries: int = 3) -> Any:
        """GET with rate limiting, caching and backoff on 429."""
        if self._client is None:
            raise CoinGeckoError("Client used outside of an async context manager.")

        cache_key = f"{path}?{sorted((params or {}).items())}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        for attempt in range(retries):
            await self.limiter.acquire()
            try:
                response = await self._client.get(path, params=params)
            except httpx.HTTPError as exc:  # network level
                last_error = exc
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code == 429:
                # Back off harder than the limiter alone would.
                await asyncio.sleep(5 * (attempt + 1))
                last_error = CoinGeckoError("CoinGecko rate limit reached (HTTP 429).")
                continue

            if response.status_code >= 400:
                raise CoinGeckoError(
                    f"CoinGecko returned HTTP {response.status_code} for {path}."
                )

            payload = response.json()
            ttl = HISTORY_CACHE_TTL if "market_chart" in path else MARKET_CACHE_TTL
            self.cache.set(cache_key, payload, ttl)
            return payload

        raise CoinGeckoError(f"CoinGecko request failed after {retries} attempts: {last_error}")

    async def markets(self, ids: list[str]) -> list[dict]:
        """Current market snapshot for the given coin ids.

        One call regardless of how many ids are passed, up to 250.
        """
        if not ids:
            return []
        payload = await self._get(
            "/coins/markets",
            {
                "vs_currency": "usd",
                "ids": ",".join(ids),
                "order": "market_cap_desc",
                "per_page": 250,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h,7d",
            },
        )
        return payload if isinstance(payload, list) else []

    async def market_chart(self, coin_id: str, days: int = 90) -> dict:
        """Daily price and volume history for one coin.

        ``interval=daily`` is requested explicitly so the series is one point
        per day rather than hourly, which keeps the payload small and the
        statistics meaningful.
        """
        payload = await self._get(
            f"/coins/{coin_id}/market_chart",
            {"vs_currency": "usd", "days": days, "interval": "daily"},
        )
        return payload if isinstance(payload, dict) else {}

    async def history_frame(
        self, coin_id: str, days: int = 90, drop_partial_day: bool = True
    ):
        """Return a tidy DataFrame of ``date``, ``price``, ``volume``.

        The final point CoinGecko returns is the *current* day, which is only
        partly elapsed. Its volume is a running total, so it is always lower
        than a completed day's and would make the volume detector under-react
        on the most recent observation. It is dropped by default.

        Imported lazily so the module can be read without pandas installed.
        """
        import pandas as pd

        payload = await self.market_chart(coin_id, days)
        prices = payload.get("prices") or []
        volumes = payload.get("total_volumes") or []

        if not prices:
            return pd.DataFrame(columns=["date", "price", "volume"])

        price_frame = pd.DataFrame(prices, columns=["ts", "price"])
        volume_frame = pd.DataFrame(volumes, columns=["ts", "volume"])

        frame = price_frame.merge(volume_frame, on="ts", how="left")
        frame["date"] = pd.to_datetime(frame["ts"], unit="ms", utc=True)
        frame = frame[["date", "price", "volume"]].dropna(subset=["price"])
        frame["volume"] = frame["volume"].fillna(0.0)
        frame = frame.sort_values("date").reset_index(drop=True)

        if drop_partial_day and len(frame) > 1:
            last = frame["date"].iloc[-1]
            # A daily series should land on midnight. Anything later is the
            # in-progress day.
            if last.hour or last.minute or last.second:
                frame = frame.iloc[:-1].reset_index(drop=True)

        return frame

"""FastAPI detection engine.

Endpoints
---------
GET  /api/health          liveness plus cache stats
GET  /api/assets          tracked assets and current market snapshot
GET  /api/anomalies       detected events, filterable
GET  /api/series/{id}     price and volume series with event markers
GET  /api/backtest        replay over a window, per asset
GET  /api/digest          daily summary of what fired
GET  /api/compare         two assets side by side
GET  /api/export.csv      flagged events as CSV
GET  /api/config          the detector thresholds currently in force

Everything is read-only and unauthenticated. There is no database, no user
account, and nothing to sign up for.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from engine.assets import MAX_ASSETS, tracked_assets
from engine.backtest import run_backtest
from engine.coingecko import CoinGeckoClient, CoinGeckoError
from engine.config import DetectorConfig
from engine.detectors import AnomalyEvent, detect_anomalies, summarise
from engine.digest import build_digest

app = FastAPI(
    title="Crypto Open-Data Anomaly Detector",
    description=(
        "Statistical anomaly detection over CoinGecko public market data. "
        "Not machine learning. Not a price prediction."
    ),
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def strip_api_prefix(request, call_next):
    """Make the app work whether or not the host strips the ``/api`` prefix.

    Vercel serves a file-based Python function at its file path, so
    ``api/index.py`` is reachable at ``/api``. Whether the ASGI app then sees
    ``/api/health`` or ``/health`` depends on the host, and getting this wrong
    produces a 404 that is hard to diagnose from the outside.

    Rather than guess, the routes are declared without a prefix and this
    middleware removes a leading ``/api`` when it is present. The app is then
    correct under both arrangements, and also under ``uvicorn`` locally where
    there is no prefix at all.
    """
    path = request.scope.get("path", "")
    if path == "/api":
        request.scope["path"] = "/"
    elif path.startswith("/api/"):
        request.scope["path"] = path[len("/api") :]
    return await call_next(request)

# One client per warm instance, so the rate limiter and cache are shared
# across requests instead of being rebuilt every time.
_client: CoinGeckoClient | None = None
_client_lock = asyncio.Lock()


def _calls_per_minute() -> int:
    raw = os.environ.get("COINGECKO_CALLS_PER_MINUTE", "").strip()
    try:
        return max(1, int(raw)) if raw else 10
    except ValueError:
        return 10


async def get_client() -> CoinGeckoClient:
    """Return the shared client, creating it on first use."""
    global _client
    async with _client_lock:
        if _client is None:
            _client = CoinGeckoClient(calls_per_minute=_calls_per_minute())
            await _client.__aenter__()
        return _client


def _config() -> DetectorConfig:
    return DetectorConfig.from_env()


async def _load_asset_events(
    asset: dict[str, str], days: int, cfg: DetectorConfig
) -> tuple[list[AnomalyEvent], list[dict]]:
    """Fetch one asset's history and run the detectors over it."""
    client = await get_client()
    frame = await client.history_frame(asset["id"], days=days)
    events = detect_anomalies(frame, asset["id"], asset["symbol"], cfg)

    series = [
        {
            "date": row.date.isoformat(),
            "price": float(row.price),
            "volume": float(row.volume),
        }
        for row in frame.itertuples()
    ]
    return events, series


@app.get("/")
async def root() -> dict:
    """Landing response, so hitting the function root is not a 404."""
    return {
        "name": "Crypto Open-Data Anomaly Detector",
        "version": "1.1.0",
        "kind": "statistical anomaly detection",
        "not": ["machine learning", "a price prediction", "investment advice"],
        "endpoints": [
            "/health",
            "/config",
            "/assets",
            "/anomalies",
            "/series/{coin_id}",
            "/backtest",
            "/digest",
            "/compare",
            "/export.csv",
        ],
    }


@app.get("/health")
async def health() -> dict:
    """Liveness check. Also reports cache occupancy, which is useful when
    diagnosing whether a slow response was a cache miss or a rate limit."""
    client = await get_client()
    return {
        "status": "ok",
        "time": datetime.now(UTC).isoformat(),
        "cache": client.cache.stats(),
        "calls_per_minute": _calls_per_minute(),
        "tracked_assets": len(tracked_assets()),
        "max_assets": MAX_ASSETS,
    }


@app.get("/config")
async def config() -> dict:
    """The detector thresholds currently in force.

    Exposed so a reader can see exactly what numbers produced the flags,
    rather than having to trust a black box.
    """
    return {
        "detector": _config().to_dict(),
        "disclaimer": (
            "Statistical anomaly detection. Not machine learning, not AI, "
            "and not a price prediction."
        ),
    }


@app.get("/assets")
async def assets() -> dict:
    """Tracked assets with their current market snapshot."""
    tracked = tracked_assets()
    client = await get_client()
    try:
        markets = await client.markets([a["id"] for a in tracked])
    except CoinGeckoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    by_id = {m.get("id"): m for m in markets}
    payload = []
    for asset in tracked:
        market = by_id.get(asset["id"], {})
        payload.append(
            {
                "id": asset["id"],
                "symbol": asset["symbol"],
                "name": asset["name"],
                "price": market.get("current_price"),
                "market_cap": market.get("market_cap"),
                "volume_24h": market.get("total_volume"),
                "change_24h": market.get("price_change_percentage_24h"),
                "change_7d": market.get("price_change_percentage_7d_in_currency"),
            }
        )
    return {"assets": payload, "count": len(payload)}


@app.get("/anomalies")
async def anomalies(
    days: int = Query(90, ge=7, le=365),
    severity: str | None = Query(None, description="watch, notable or extreme"),
    asset: str | None = Query(None, description="CoinGecko id, e.g. bitcoin"),
    kind: str | None = Query(None, description="price_zscore, volume_spike or volatility_regime"),
) -> dict:
    """Detected events across the tracked assets, with optional filters."""
    cfg = _config()
    tracked = tracked_assets()
    if asset:
        tracked = [a for a in tracked if a["id"] == asset.lower()]
        if not tracked:
            raise HTTPException(status_code=404, detail=f"Asset '{asset}' is not tracked.")

    all_events: list[AnomalyEvent] = []
    errors: list[str] = []

    for item in tracked:
        try:
            events, _ = await _load_asset_events(item, days, cfg)
            all_events.extend(events)
        except CoinGeckoError as exc:
            errors.append(f"{item['id']}: {exc}")

    if severity:
        wanted = severity.lower()
        all_events = [e for e in all_events if e.severity == wanted]
    if kind:
        wanted_kind = kind.lower()
        all_events = [e for e in all_events if e.kind == wanted_kind]

    all_events.sort(key=lambda e: e.timestamp, reverse=True)

    return {
        "events": [e.to_dict() for e in all_events],
        "summary": summarise(all_events),
        "filters": {"days": days, "severity": severity, "asset": asset, "kind": kind},
        "errors": errors,
        "disclaimer": "Statistical flags, not predictions.",
    }


@app.get("/series/{coin_id}")
async def series(coin_id: str, days: int = Query(90, ge=7, le=365)) -> dict:
    """Price and volume series for one asset, with its events attached.

    The dashboard draws the line from ``series`` and the markers from
    ``events``, so the chart and the table can never disagree.
    """
    cfg = _config()
    tracked = {a["id"]: a for a in tracked_assets()}
    asset = tracked.get(coin_id.lower())
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{coin_id}' is not tracked.")

    try:
        events, points = await _load_asset_events(asset, days, cfg)
    except CoinGeckoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "asset": asset,
        "days": days,
        "series": points,
        "events": [e.to_dict() for e in events],
        "summary": summarise(events),
    }


@app.get("/backtest")
async def backtest(
    days: int = Query(90, ge=30, le=365),
    asset: str | None = Query(None),
) -> dict:
    """Replay the detectors and report how many alerts would have fired.

    This is the credibility endpoint. It reports the false-positive load
    rather than hiding it, and it makes no claim about profitability.
    """
    cfg = _config()
    tracked = tracked_assets()
    if asset:
        tracked = [a for a in tracked if a["id"] == asset.lower()]
        if not tracked:
            raise HTTPException(status_code=404, detail=f"Asset '{asset}' is not tracked.")

    results = []
    errors: list[str] = []
    for item in tracked:
        try:
            client = await get_client()
            frame = await client.history_frame(item["id"], days=days)
            result = run_backtest(frame, item["id"], item["symbol"], days, cfg)
            results.append(result.to_dict(include_events=True))
        except CoinGeckoError as exc:
            errors.append(f"{item['id']}: {exc}")

    total = sum(r["total_events"] for r in results)
    weeks = max(days / 7.0, 1e-9)

    return {
        "days": days,
        "assets": results,
        "totals": {
            "events": total,
            "events_per_week": round(total / weeks, 2),
            "assets": len(results),
        },
        "errors": errors,
        "note": (
            "Counts of statistical flags over a historical window. This is a "
            "false-positive load measurement, not a performance or accuracy "
            "claim. The detectors make no prediction."
        ),
    }


@app.get("/digest")
async def digest(
    hours: int = Query(24, ge=1, le=168),
    days: int = Query(90, ge=7, le=365),
) -> dict:
    """Daily summary of what fired, as structured data and as plain text."""
    cfg = _config()
    all_events: list[AnomalyEvent] = []
    errors: list[str] = []

    for item in tracked_assets():
        try:
            events, _ = await _load_asset_events(item, days, cfg)
            all_events.extend(events)
        except CoinGeckoError as exc:
            errors.append(f"{item['id']}: {exc}")

    payload = build_digest(all_events, window_hours=hours)
    payload["errors"] = errors
    return payload


@app.get("/compare")
async def compare(
    a: str = Query(..., description="First CoinGecko id"),
    b: str = Query(..., description="Second CoinGecko id"),
    days: int = Query(90, ge=7, le=365),
) -> dict:
    """Two assets side by side, each with its own series and events."""
    cfg = _config()
    tracked = {x["id"]: x for x in tracked_assets()}

    out: dict[str, dict] = {}
    for key, coin_id in (("a", a.lower()), ("b", b.lower())):
        asset = tracked.get(coin_id)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Asset '{coin_id}' is not tracked.")
        try:
            events, points = await _load_asset_events(asset, days, cfg)
        except CoinGeckoError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        out[key] = {
            "asset": asset,
            "series": points,
            "events": [e.to_dict() for e in events],
            "summary": summarise(events),
        }

    return {"days": days, "a": out["a"], "b": out["b"]}


@app.get("/export.csv")
async def export_csv(
    days: int = Query(90, ge=7, le=365),
    severity: str | None = Query(None),
    asset: str | None = Query(None),
) -> StreamingResponse:
    """Flagged events as a CSV download."""
    cfg = _config()
    tracked = tracked_assets()
    if asset:
        tracked = [x for x in tracked if x["id"] == asset.lower()]
        if not tracked:
            raise HTTPException(status_code=404, detail=f"Asset '{asset}' is not tracked.")

    all_events: list[AnomalyEvent] = []
    for item in tracked:
        try:
            events, _ = await _load_asset_events(item, days, cfg)
            all_events.extend(events)
        except CoinGeckoError:
            continue

    if severity:
        all_events = [e for e in all_events if e.severity == severity.lower()]
    all_events.sort(key=lambda e: e.timestamp, reverse=True)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["asset_id", "symbol", "kind", "timestamp", "severity", "value", "baseline", "score", "direction", "detail"]
    )
    for event in all_events:
        writer.writerow(
            [
                event.asset_id,
                event.symbol,
                event.kind,
                event.timestamp,
                event.severity,
                event.value,
                event.baseline,
                event.score,
                event.direction,
                event.detail,
            ]
        )
    buffer.seek(0)

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="anomalies-{stamp}.csv"'},
    )

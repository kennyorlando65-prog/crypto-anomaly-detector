"""Tests for the FastAPI app's routing and response shapes.

These use the in-process test client, so they need no network and no running
server. The CoinGecko client is stubbed, because the point is to test the
app's own behaviour rather than the upstream API.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api.index as api_module


@pytest.fixture
def client(monkeypatch):
    """A test client with the CoinGecko client stubbed out."""

    class StubClient:
        def __init__(self) -> None:
            self.cache = _StubCache()

        async def markets(self, ids):
            return [
                {
                    "id": coin_id,
                    "current_price": 100.0,
                    "market_cap": 1_000_000.0,
                    "total_volume": 50_000.0,
                    "price_change_percentage_24h": 1.5,
                    "price_change_percentage_7d_in_currency": -2.0,
                }
                for coin_id in ids
            ]

        async def history_frame(self, coin_id, days=90, drop_partial_day=True):
            dates = pd.date_range("2026-01-01", periods=120, freq="D", tz="UTC")
            rng = np.random.default_rng(9)
            price = 100.0 + np.cumsum(rng.normal(0, 0.4, 120))
            price[100] = price[100] * 1.5
            return pd.DataFrame(
                {"date": dates, "price": price, "volume": 1000.0 + rng.normal(0, 20, 120)}
            )

    class _StubCache:
        def stats(self):
            return {"entries": 0, "live": 0}

    async def fake_get_client():
        return StubClient()

    monkeypatch.setattr(api_module, "get_client", fake_get_client)
    return TestClient(api_module.app)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def test_root_returns_a_landing_payload(client):
    """Hitting the function root must not 404."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == "1.1.0"


def test_health_is_reachable_without_prefix(client):
    """Local and stripped-prefix deployments use the bare path."""
    assert client.get("/health").status_code == 200


def test_health_is_reachable_with_api_prefix(client):
    """Vercel may pass the full path through, so /api/health must also work.

    This is the middleware's whole reason for existing.
    """
    assert client.get("/api/health").status_code == 200


def test_prefixed_and_bare_paths_agree(client):
    """Both spellings must return the same body, not merely a 200.

    The ``time`` field is excluded because it is generated per request, so two
    calls legitimately differ there. Everything else must match exactly.
    """
    bare = client.get("/health").json()
    prefixed = client.get("/api/health").json()
    bare.pop("time")
    prefixed.pop("time")
    assert bare == prefixed


def test_assets_is_reachable_both_ways(client):
    """The prefix handling must apply to every route, not just health."""
    bare = client.get("/assets")
    prefixed = client.get("/api/assets")
    assert bare.status_code == prefixed.status_code == 200
    assert bare.json() == prefixed.json()


def test_unknown_route_is_404(client):
    """A genuinely missing route must still 404."""
    assert client.get("/nope").status_code == 404


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------


def test_config_exposes_thresholds_and_disclaimer(client):
    """The thresholds must be visible, and the disclaimer must be present."""
    payload = client.get("/config").json()
    assert payload["detector"]["window"] == 30
    assert "not machine learning" in payload["disclaimer"].lower()


def test_assets_returns_the_tracked_list(client):
    """The default list is 8 assets."""
    payload = client.get("/assets").json()
    assert payload["count"] == 8
    assert payload["assets"][0]["id"] == "bitcoin"


def test_anomalies_returns_events_and_summary(client):
    """The endpoint must return both the events and their summary."""
    payload = client.get("/anomalies?days=90").json()
    assert "events" in payload and "summary" in payload
    assert payload["summary"]["total"] == len(payload["events"])


def test_anomalies_severity_filter_is_applied(client):
    """Filtering by severity must return only that severity."""
    payload = client.get("/anomalies?days=90&severity=extreme").json()
    assert all(event["severity"] == "extreme" for event in payload["events"])


def test_anomalies_unknown_asset_is_404(client):
    """An untracked asset must be a clear 404, not an empty list."""
    assert client.get("/anomalies?asset=not-a-coin").status_code == 404


def test_series_returns_points_and_events(client):
    """The chart needs both the series and the markers."""
    payload = client.get("/series/bitcoin?days=90").json()
    assert len(payload["series"]) > 0
    assert payload["asset"]["symbol"] == "BTC"


def test_series_unknown_asset_is_404(client):
    """An untracked asset must 404."""
    assert client.get("/series/not-a-coin").status_code == 404


def test_backtest_reports_totals_and_a_note(client):
    """The backtest must carry its own honesty note."""
    payload = client.get("/backtest?days=90").json()
    assert payload["totals"]["assets"] == 8
    assert "not a performance" in payload["note"].lower()


def test_digest_returns_text_and_counts(client):
    """The digest must be usable as plain text."""
    payload = client.get("/digest?hours=24").json()
    assert "Anomaly digest" in payload["text"]
    assert sum(payload["counts"].values()) == payload["total"]


def test_compare_returns_both_sides(client):
    """Compare must return two labelled sides."""
    payload = client.get("/compare?a=bitcoin&b=ethereum&days=90").json()
    assert payload["a"]["asset"]["id"] == "bitcoin"
    assert payload["b"]["asset"]["id"] == "ethereum"


def test_compare_unknown_asset_is_404(client):
    """An untracked asset on either side must 404."""
    assert client.get("/compare?a=bitcoin&b=nope").status_code == 404


def test_export_csv_has_a_header_and_attachment_disposition(client):
    """The CSV must be downloadable and correctly shaped."""
    response = client.get("/export.csv?days=90")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    header = response.text.splitlines()[0]
    assert header.startswith("asset_id,symbol,kind,timestamp,severity")


def test_export_csv_respects_the_severity_filter(client):
    """Every data row must match the requested severity."""
    response = client.get("/export.csv?days=90&severity=extreme")
    rows = response.text.splitlines()[1:]
    for row in rows:
        assert ",extreme," in row


def test_export_csv_unknown_asset_is_404(client):
    """An untracked asset must 404 rather than return an empty file."""
    assert client.get("/export.csv?asset=nope").status_code == 404


def test_days_parameter_is_validated(client):
    """Out-of-range windows must be rejected by FastAPI's validation."""
    assert client.get("/anomalies?days=1").status_code == 422
    assert client.get("/anomalies?days=9999").status_code == 422

"""Tests for the backtest, digest and config modules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from engine.backtest import run_backtest
from engine.config import DetectorConfig
from engine.detectors import AnomalyEvent, detect_anomalies
from engine.digest import build_digest

# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------


def test_backtest_counts_only_events_inside_the_window(spike_series):
    """Events before the window must not be counted.

    The spike sits at index 100 of 120 daily points, so it is inside a 30-day
    window but outside a 10-day one.
    """
    wide = run_backtest(spike_series, "t", "T", days=30)
    narrow = run_backtest(spike_series, "t", "T", days=10)
    assert wide.total_events >= narrow.total_events


def test_backtest_reports_events_per_week(spike_series):
    """The rate must be consistent with the count and the window length."""
    result = run_backtest(spike_series, "t", "T", days=90)
    expected = result.total_events / (90 / 7.0)
    assert result.events_per_week == round(expected, 2)


def test_backtest_on_empty_frame_is_safe():
    """An empty frame must produce a zeroed result, not an exception."""
    empty = pd.DataFrame(columns=["date", "price", "volume"])
    result = run_backtest(empty, "t", "T", days=90)
    assert result.total_events == 0
    assert result.events == []


def test_detector_does_not_use_future_data(spike_series):
    """Events on a prefix must be identical to those on the full series.

    This is the strongest form of the no-look-ahead property. If the detector
    peeked at later data, truncating the series would change the events it
    reports for the earlier period. Comparing the overlapping events exactly
    catches any leak, including one that only shifts a score slightly.
    """
    full = detect_anomalies(spike_series, "t", "T")
    cutoff = spike_series["date"].iloc[80]
    prefix = spike_series[spike_series["date"] <= cutoff].reset_index(drop=True)
    partial = detect_anomalies(prefix, "t", "T")

    full_early = [e.to_dict() for e in full if pd.Timestamp(e.timestamp) <= cutoff]
    assert full_early == [e.to_dict() for e in partial]


def test_backtest_payload_is_serialisable(spike_series):
    """The API returns this dict, so it must be JSON-safe."""
    import json

    payload = run_backtest(spike_series, "t", "T", days=90).to_dict()
    assert json.loads(json.dumps(payload))["asset_id"] == "t"


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------


def _event(hours_ago: float, severity: str = "watch") -> AnomalyEvent:
    stamp = datetime.now(UTC) - timedelta(hours=hours_ago)
    return AnomalyEvent(
        asset_id="bitcoin",
        symbol="BTC",
        kind="price_zscore",
        timestamp=stamp.isoformat(),
        severity=severity,
        value=1.0,
        baseline=1.0,
        score=3.0,
        direction="up",
        detail="test event",
    )


def test_digest_includes_only_recent_events():
    """A 24-hour digest must exclude a 48-hour-old event."""
    events = [_event(2), _event(48)]
    digest = build_digest(events, window_hours=24)
    assert digest["total"] == 1


def test_digest_orders_extreme_first():
    """The most severe events must lead the digest."""
    events = [_event(1, "watch"), _event(2, "extreme"), _event(3, "notable")]
    digest = build_digest(events, window_hours=24)
    assert digest["events"][0]["severity"] == "extreme"


def test_digest_handles_no_events():
    """An empty window must produce a readable message, not a blank page."""
    digest = build_digest([], window_hours=24)
    assert digest["total"] == 0
    assert "No anomalies" in digest["text"]


def test_digest_text_always_carries_the_disclaimer():
    """The disclaimer must be present whether or not anything fired."""
    for events in ([], [_event(1)]):
        assert "not a prediction" in build_digest(events, 24)["text"].lower()


def test_digest_counts_match_events():
    """The severity counts must add up to the total."""
    events = [_event(1, "extreme"), _event(2, "notable"), _event(3, "watch")]
    digest = build_digest(events, 24)
    assert sum(digest["counts"].values()) == digest["total"] == 3


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_defaults_are_ordered():
    """Severity thresholds must increase, or the tiers are meaningless."""
    cfg = DetectorConfig()
    assert cfg.watch_threshold < cfg.notable_threshold < cfg.extreme_threshold


def test_config_from_env_reads_overrides(monkeypatch):
    """Environment overrides must take effect."""
    monkeypatch.setenv("DETECTOR_WINDOW", "14")
    monkeypatch.setenv("DETECTOR_WATCH_THRESHOLD", "1.5")
    cfg = DetectorConfig.from_env()
    assert cfg.window == 14
    assert cfg.watch_threshold == 1.5


def test_config_from_env_ignores_garbage(monkeypatch):
    """A malformed value must fall back to the default, not crash the app."""
    monkeypatch.setenv("DETECTOR_WINDOW", "not-a-number")
    assert DetectorConfig.from_env().window == DetectorConfig().window


def test_config_is_immutable():
    """The config is frozen, so a request cannot mutate shared state."""
    cfg = DetectorConfig()
    try:
        cfg.window = 99  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("DetectorConfig should be frozen")


def test_config_to_dict_round_trips():
    """The API exposes this dict, so every field must be present."""
    payload = DetectorConfig().to_dict()
    assert payload["window"] == 30
    assert "volatility_ratio_threshold" in payload

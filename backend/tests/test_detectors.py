"""Tests for the statistical detectors.

These tests assert behaviour, not implementation. Each one states a property
that must hold for the detector to be trustworthy, and the negative tests
matter more than the positive ones: a detector that fires on everything is
worse than useless.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.config import DetectorConfig
from engine.detectors import (
    classify_severity,
    detect_anomalies,
    rolling_zscore,
    summarise,
    volatility_regime_ratio,
    volume_spike_score,
)

# ---------------------------------------------------------------------------
# Rolling z-score
# ---------------------------------------------------------------------------


def test_zscore_excludes_current_point_from_its_own_baseline():
    """The baseline must not include the point being scored.

    This is the look-ahead guard. The baseline is a tight band around 10 with
    a standard deviation near 0.1, and the final value is 1000. Excluding the
    final point gives a z-score in the thousands. Including it would drag the
    mean up to roughly 42 and inflate the standard deviation to roughly 178,
    collapsing the z-score to about 5. The assertion is set well above that
    cheating value so the two behaviours cannot be confused.
    """
    rng = np.random.default_rng(0)
    base = list(10.0 + rng.normal(0, 0.1, 30))
    series = pd.Series(base + [1000.0])
    z = rolling_zscore(series, window=30, min_periods=10)
    assert z.iloc[-1] > 100.0, "spike was hidden by its own baseline"


def test_zscore_is_nan_before_min_periods():
    """No baseline means no score. Early points must be NaN, not zero."""
    series = pd.Series(np.arange(20, dtype=float))
    z = rolling_zscore(series, window=10, min_periods=10)
    assert z.iloc[:10].isna().all()
    assert z.iloc[10:].notna().all()


def test_zscore_flat_series_is_nan_not_infinite():
    """A zero-variance baseline carries no information, so it yields NaN."""
    series = pd.Series([5.0] * 40)
    z = rolling_zscore(series, window=10, min_periods=5)
    assert not np.isinf(z.dropna()).any()
    assert z.dropna().empty


def test_zscore_sign_follows_direction():
    """A downward move must score negative, an upward move positive."""
    rng = np.random.default_rng(1)
    base = list(10.0 + rng.normal(0, 0.1, 30))
    up = pd.Series(base + [50.0])
    down = pd.Series(base + [1.0])
    assert rolling_zscore(up, 30, 10).iloc[-1] > 0
    assert rolling_zscore(down, 30, 10).iloc[-1] < 0


def test_robust_zscore_uses_median_and_mad():
    """The robust variant must survive an outlier in the baseline window.

    A single 10000 in the baseline drags the plain mean to roughly 354 and
    inflates the standard deviation to roughly 1850, so a genuinely unusual
    value of 12 scores near zero. The median and MAD ignore the outlier, so
    the same value scores far higher. That difference is the whole point of
    offering the robust mode.
    """
    rng = np.random.default_rng(2)
    base = list(10.0 + rng.normal(0, 0.5, 28))
    series = pd.Series(base + [10000.0] + [12.0])
    plain = rolling_zscore(series, 30, 10, robust=False).iloc[-1]
    robust = rolling_zscore(series, 30, 10, robust=True).iloc[-1]
    assert np.isfinite(robust), "robust z-score must not be NaN"
    assert abs(robust) > abs(plain)


def test_robust_zscore_is_finite_inside_the_first_window():
    """The shifted baseline starts with a NaN, which must not poison the MAD.

    Every window that reaches back to the first observation contains that
    NaN. ``rolling.std`` skips it; ``rolling.apply`` does not, so this guards
    the explicit filtering in the MAD helper.
    """
    rng = np.random.default_rng(4)
    series = pd.Series(10.0 + rng.normal(0, 0.5, 40))
    z = rolling_zscore(series, 30, 10, robust=True)
    assert z.iloc[10:].notna().all(), "robust z-score went NaN inside the window"


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------


def test_volume_ratio_is_one_for_constant_volume():
    """Constant volume means today equals the average, so the ratio is 1."""
    volume = pd.Series([500.0] * 40)
    ratio = volume_spike_score(volume, window=10, min_periods=5)
    assert ratio.dropna().iloc[-1] == pytest.approx(1.0)


def test_volume_ratio_detects_a_spike():
    """A 10x day must produce a ratio near 10."""
    volume = pd.Series([100.0] * 30 + [1000.0])
    ratio = volume_spike_score(volume, window=30, min_periods=10)
    assert ratio.iloc[-1] == pytest.approx(10.0, rel=0.01)


def test_volume_ratio_excludes_current_point():
    """The spike must not dilute its own baseline."""
    volume = pd.Series([100.0] * 30 + [1000.0])
    ratio = volume_spike_score(volume, window=30, min_periods=10)
    # If the spike were included, the mean would be ~129 and the ratio ~7.7.
    assert ratio.iloc[-1] > 9.0


# ---------------------------------------------------------------------------
# Volatility regime
# ---------------------------------------------------------------------------


def test_volatility_ratio_near_one_when_volatility_is_stable():
    """Stable volatility means short and long windows agree."""
    rng = np.random.default_rng(1)
    price = pd.Series(100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, 200))))
    ratio = volatility_regime_ratio(price, 7, 30, min_periods=5)
    assert 0.3 < ratio.dropna().iloc[-1] < 3.0


def test_volatility_ratio_detects_a_regime_change():
    """A sudden jump in volatility must push the ratio well above 1.

    The burst is short on purpose. A long high-volatility stretch would
    dominate the 30-day baseline's own standard deviation and pull the ratio
    back toward 1, which is a genuine property of a regime-change detector:
    it measures a change, so the new regime has to be recent.
    """
    rng = np.random.default_rng(2)
    returns = np.concatenate([rng.normal(0, 0.002, 114), rng.normal(0, 0.09, 6)])
    price = pd.Series(100.0 * np.exp(np.cumsum(returns)))
    ratio = volatility_regime_ratio(price, 7, 30, min_periods=5)
    assert ratio.dropna().iloc[-1] > 2.0


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


def test_severity_tiers_are_ordered():
    """Each threshold must map to its own tier, and below watch is None."""
    cfg = DetectorConfig()
    assert classify_severity(1.0, cfg) is None
    assert classify_severity(2.5, cfg) == "watch"
    assert classify_severity(3.5, cfg) == "notable"
    assert classify_severity(5.0, cfg) == "extreme"


def test_severity_is_symmetric_for_negative_scores():
    """A crash is as notable as a pump."""
    cfg = DetectorConfig()
    assert classify_severity(-5.0, cfg) == "extreme"
    assert classify_severity(-2.5, cfg) == "watch"


def test_severity_handles_nan_and_none():
    """Missing scores must not raise, and must not be flagged."""
    cfg = DetectorConfig()
    assert classify_severity(float("nan"), cfg) is None
    assert classify_severity(None, cfg) is None


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


def test_flat_series_produces_no_events(flat_series):
    """The critical negative test: no structure means no alerts."""
    events = detect_anomalies(flat_series, "test", "TST")
    assert events == []


def test_calm_series_produces_few_events(calm_series):
    """Ordinary noise must not light up the detector.

    The watch tier sits at two standard deviations, so on 120 days of normal
    data roughly five percent of days are expected to cross it, and there are
    three detectors. A count in the single digits is the honest expectation.
    What would be wrong is dozens, which would mean the thresholds are too
    loose to be useful.
    """
    events = detect_anomalies(calm_series, "test", "TST")
    assert len(events) <= 12, f"too noisy: {len(events)} events on calm data"


def test_price_spike_is_detected(spike_series):
    """An injected 60 percent jump must be flagged, and flagged as a price event."""
    events = detect_anomalies(spike_series, "test", "TST")
    price_events = [e for e in events if e.kind == "price_zscore"]
    assert price_events, "the injected price spike was missed"
    assert any(e.severity in {"notable", "extreme"} for e in price_events)


def test_volume_spike_is_detected(volume_spike_series):
    """An injected 12x volume day must be flagged as a volume event."""
    events = detect_anomalies(volume_spike_series, "test", "TST")
    volume_events = [e for e in events if e.kind == "volume_spike"]
    assert volume_events, "the injected volume spike was missed"
    assert volume_events[0].score > 5.0


def test_regime_change_is_detected(regime_change_series):
    """A 25x volatility jump must be flagged as a regime change."""
    events = detect_anomalies(regime_change_series, "test", "TST")
    regime_events = [e for e in events if e.kind == "volatility_regime"]
    assert regime_events, "the injected volatility regime change was missed"


def test_events_are_sorted_by_time(calm_series):
    """Output order must be deterministic and chronological."""
    events = detect_anomalies(calm_series, "test", "TST")
    stamps = [e.timestamp for e in events]
    assert stamps == sorted(stamps)


def test_cooldown_suppresses_repeat_events():
    """A sustained move must not fire once per day.

    Without a cooldown, a week-long elevated reading produces seven events
    and the backtest counts seven signals where a human counts one.
    """
    dates = pd.date_range("2026-01-01", periods=120, freq="D", tz="UTC")
    price = np.full(120, 100.0)
    price[100:110] = 200.0  # ten consecutive elevated days
    frame = pd.DataFrame({"date": dates, "price": price, "volume": np.full(120, 1000.0)})

    with_cooldown = detect_anomalies(frame, "t", "T", DetectorConfig(cooldown=3))
    without = detect_anomalies(frame, "t", "T", DetectorConfig(cooldown=0))
    assert len(with_cooldown) < len(without)


def test_empty_frame_returns_no_events():
    """An empty input must not raise."""
    empty = pd.DataFrame(columns=["date", "price", "volume"])
    assert detect_anomalies(empty, "t", "T") == []


def test_short_frame_returns_no_events():
    """Too little history for a baseline means no events, not a crash."""
    dates = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    frame = pd.DataFrame({"date": dates, "price": [1.0, 2.0, 3.0], "volume": [1.0, 2.0, 3.0]})
    assert detect_anomalies(frame, "t", "T") == []


def test_unsorted_input_is_handled(calm_series):
    """Input order must not change the result."""
    shuffled = calm_series.sample(frac=1.0, random_state=5).reset_index(drop=True)
    assert len(detect_anomalies(shuffled, "t", "T")) == len(
        detect_anomalies(calm_series, "t", "T")
    )


def test_summarise_counts_match_events(calm_series):
    """The summary must agree with the event list it describes."""
    events = detect_anomalies(calm_series, "test", "TST")
    stats = summarise(events)
    assert stats["total"] == len(events)
    assert sum(stats["by_severity"].values()) == len(events)
    assert sum(stats["by_kind"].values()) == len(events)


def test_event_payload_is_json_serialisable(spike_series):
    """Events must survive a round trip through JSON, since the API returns them."""
    import json

    events = detect_anomalies(spike_series, "test", "TST")
    assert events
    encoded = json.dumps([e.to_dict() for e in events])
    assert json.loads(encoded)[0]["asset_id"] == "test"

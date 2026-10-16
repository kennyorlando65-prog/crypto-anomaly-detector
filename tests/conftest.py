"""Shared fixtures for the test suite."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def flat_series() -> pd.DataFrame:
    """A perfectly flat series. Nothing should ever be flagged here.

    This is the most important negative test: a detector that fires on a
    constant series is broken, because a flat baseline carries no information
    about what is unusual.
    """
    dates = pd.date_range("2026-01-01", periods=120, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "date": dates,
            "price": np.full(120, 100.0),
            "volume": np.full(120, 1000.0),
        }
    )


@pytest.fixture
def calm_series() -> pd.DataFrame:
    """A gently varying series with no injected anomaly.

    Small deterministic noise, so the test is reproducible without a seed.
    """
    dates = pd.date_range("2026-01-01", periods=120, freq="D", tz="UTC")
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.5, 120)
    price = 100.0 + np.cumsum(noise)
    volume = 1000.0 + rng.normal(0, 50, 120)
    return pd.DataFrame({"date": dates, "price": price, "volume": volume})


@pytest.fixture
def spike_series() -> pd.DataFrame:
    """A calm series with one large, unambiguous price spike at index 100."""
    dates = pd.date_range("2026-01-01", periods=120, freq="D", tz="UTC")
    rng = np.random.default_rng(7)
    price = 100.0 + np.cumsum(rng.normal(0, 0.3, 120))
    price[100] = price[100] * 1.6  # a 60 percent jump in one day
    volume = 1000.0 + rng.normal(0, 30, 120)
    return pd.DataFrame({"date": dates, "price": price, "volume": volume})


@pytest.fixture
def volume_spike_series() -> pd.DataFrame:
    """A calm series with one enormous volume spike at index 100."""
    dates = pd.date_range("2026-01-01", periods=120, freq="D", tz="UTC")
    rng = np.random.default_rng(11)
    price = 100.0 + np.cumsum(rng.normal(0, 0.3, 120))
    volume = 1000.0 + rng.normal(0, 30, 120)
    volume[100] = 12000.0  # twelve times the norm
    return pd.DataFrame({"date": dates, "price": price, "volume": volume})


@pytest.fixture
def regime_change_series() -> pd.DataFrame:
    """A calm series that becomes violently jumpy in its last 6 days.

    The high-volatility stretch is deliberately short relative to the 30-day
    baseline window. A long stretch would dominate the baseline's own standard
    deviation and the ratio would stay near 1, which is a real property of the
    detector rather than a bug: it measures a *change* in regime, so the new
    regime has to be recent for the comparison to be meaningful.
    """
    dates = pd.date_range("2026-01-01", periods=120, freq="D", tz="UTC")
    rng = np.random.default_rng(3)
    returns = rng.normal(0, 0.001, 120)
    returns[-6:] = rng.normal(0, 0.09, 6)  # 90x the volatility
    price = 100.0 * np.exp(np.cumsum(returns))
    volume = 1000.0 + rng.normal(0, 30, 120)
    return pd.DataFrame({"date": dates, "price": price, "volume": volume})

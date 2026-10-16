"""Classical statistical anomaly detection for crypto market series.

WHAT THIS IS
------------
Three well-understood statistical detectors:

1. Rolling z-score on price
   Is this move large relative to the asset's own recent behaviour?
2. Volume spike
   Is this volume large relative to the asset's own recent average?
3. Volatility regime change
   Did the asset suddenly become much more jumpy than it was?

WHAT THIS IS NOT
----------------
This is not machine learning. There is no trained model, no neural network,
no learned weights, and no prediction of future prices. Every threshold is a
number a human picked and can defend. The output is a flag that says
"this observation is unusual for this asset", not "this asset will go up".

THE ONE DESIGN DECISION THAT MATTERS
------------------------------------
Every baseline is computed from data *strictly before* the point being
scored. The rolling window is shifted by one observation. This is what stops
the detector from cheating: if the current point were included in its own
baseline, a large move would inflate the mean and the standard deviation and
partially hide itself. That is look-ahead bias, and it makes backtests look
better than reality. It is avoided here on purpose.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd

from engine.config import DetectorConfig

Severity = Literal["watch", "notable", "extreme"]
DetectorKind = Literal["price_zscore", "volume_spike", "volatility_regime"]

SEVERITY_ORDER: dict[str, int] = {"watch": 0, "notable": 1, "extreme": 2}

# 1.4826 makes the MAD a consistent estimator of the standard deviation for
# normally distributed data, so a robust z-score is comparable to a plain one.
MAD_TO_SIGMA = 1.4826


def _mad(values: np.ndarray) -> float:
    """Median absolute deviation, scaled to be comparable to a std deviation.

    NaN is dropped before the median is taken. This matters because the
    baseline series is shifted by one, so its first element is always NaN and
    every window that reaches back that far would otherwise return NaN.
    ``rolling.std`` skips NaN on its own; ``rolling.apply`` does not, so the
    filtering has to happen here.
    """
    clean = values[~np.isnan(values)]
    if clean.size == 0:
        return float("nan")
    median = np.median(clean)
    return float(np.median(np.abs(clean - median))) * MAD_TO_SIGMA


@dataclass
class AnomalyEvent:
    """A single flagged observation.

    Attributes:
        asset_id: CoinGecko id, e.g. ``bitcoin``.
        symbol: Ticker, e.g. ``BTC``.
        kind: Which detector fired.
        timestamp: ISO-8601 date of the observation.
        severity: ``watch``, ``notable`` or ``extreme``.
        value: The observed value that was flagged.
        baseline: The baseline the value was compared against.
        score: The detector's score (z-score, or a ratio).
        direction: ``up`` or ``down``.
        detail: One human-readable sentence explaining the flag.
    """

    asset_id: str
    symbol: str
    kind: DetectorKind
    timestamp: str
    severity: Severity
    value: float
    baseline: float
    score: float
    direction: str
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _baseline(
    series: pd.Series,
    window: int,
    min_periods: int,
    robust: bool,
) -> tuple[pd.Series, pd.Series]:
    """Return (centre, scale) of the trailing window, excluding the current point.

    ``series.shift(1)`` is the whole trick: the window that scores observation
    *t* contains observations up to *t-1* only.
    """
    prior = series.shift(1)
    rolling = prior.rolling(window=window, min_periods=min_periods)

    if robust:
        centre = rolling.median()
        scale = rolling.apply(_mad, raw=True)
    else:
        centre = rolling.mean()
        scale = rolling.std(ddof=1)

    return centre, scale


def rolling_zscore(
    series: pd.Series,
    window: int = 30,
    min_periods: int = 10,
    robust: bool = False,
) -> pd.Series:
    """Z-score of each point against its own trailing window.

    A zero scale (a perfectly flat window) yields NaN rather than infinity,
    because a flat baseline carries no information about what is unusual.
    """
    centre, scale = _baseline(series, window, min_periods, robust)
    scale = scale.replace(0.0, np.nan)
    return (series - centre) / scale


def volume_spike_score(
    volume: pd.Series,
    window: int = 30,
    min_periods: int = 10,
) -> pd.Series:
    """Ratio of current volume to the mean of the trailing window.

    A ratio of 3.0 means today's volume is three times the recent average.
    """
    prior = volume.shift(1)
    baseline = prior.rolling(window=window, min_periods=min_periods).mean()
    baseline = baseline.replace(0.0, np.nan)
    return volume / baseline


def volatility_regime_ratio(
    close: pd.Series,
    short_window: int = 7,
    long_window: int = 30,
    min_periods: int = 5,
) -> pd.Series:
    """Ratio of recent realised volatility to longer-run realised volatility.

    Volatility is the standard deviation of daily log returns. A ratio of 2.0
    means the asset is twice as jumpy as its own recent norm.
    """
    log_returns = np.log(close / close.shift(1))
    short_vol = log_returns.rolling(short_window, min_periods=min_periods).std(ddof=1)
    long_vol = log_returns.rolling(long_window, min_periods=min_periods).std(ddof=1)
    long_vol = long_vol.replace(0.0, np.nan)
    return short_vol / long_vol


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


def classify_severity(score: float, cfg: DetectorConfig) -> Severity | None:
    """Map an absolute score onto a severity tier, or None if it is unremarkable."""
    if score is None or not np.isfinite(score):
        return None
    magnitude = abs(float(score))
    if magnitude >= cfg.extreme_threshold:
        return "extreme"
    if magnitude >= cfg.notable_threshold:
        return "notable"
    if magnitude >= cfg.watch_threshold:
        return "watch"
    return None


def _severity_from_ratio(ratio: float, threshold: float) -> Severity | None:
    """Severity for ratio-based detectors, which have no natural z-scale.

    The threshold itself is ``watch``. Twice the threshold is ``notable``,
    three times is ``extreme``. This keeps the tiers comparable across
    detectors without pretending a volume ratio is a z-score.
    """
    if ratio is None or not np.isfinite(ratio) or ratio < threshold:
        return None
    multiple = ratio / threshold
    if multiple >= 3.0:
        return "extreme"
    if multiple >= 2.0:
        return "notable"
    return "watch"


# ---------------------------------------------------------------------------
# Event extraction
# ---------------------------------------------------------------------------


def _apply_cooldown(
    events: list[AnomalyEvent], cooldown: int
) -> list[AnomalyEvent]:
    """Collapse runs of the same detector on the same asset into one event.

    Without this, a single week-long move fires seven alerts and the backtest
    counts seven "signals" where a human would count one. Events are already
    sorted by time, so a simple last-seen index is enough.
    """
    if cooldown <= 0:
        return events

    kept: list[AnomalyEvent] = []
    last_index: dict[tuple[str, str], int] = {}

    for event in events:
        key = (event.asset_id, event.kind)
        index = int(pd.Timestamp(event.timestamp).value // 10**9 // 86400)
        previous = last_index.get(key)
        if previous is not None and index - previous <= cooldown:
            # Same detector, same asset, inside the cooldown. Keep the stronger
            # of the two so the surviving event is the most severe one.
            if kept and SEVERITY_ORDER[event.severity] > SEVERITY_ORDER[kept[-1].severity]:
                kept[-1] = event
                last_index[key] = index
            continue
        kept.append(event)
        last_index[key] = index

    return kept


def detect_anomalies(
    frame: pd.DataFrame,
    asset_id: str,
    symbol: str,
    cfg: DetectorConfig | None = None,
) -> list[AnomalyEvent]:
    """Run all three detectors over one asset's daily series.

    Args:
        frame: DataFrame with ``date``, ``price`` and ``volume`` columns,
            sorted ascending by date.
        asset_id: CoinGecko id for the asset.
        symbol: Ticker for the asset.
        cfg: Detector configuration. Defaults are used when omitted.

    Returns:
        Events sorted by timestamp, then by severity (strongest first).
    """
    cfg = cfg or DetectorConfig()

    if frame is None or frame.empty:
        return []

    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], utc=True)
    data = data.sort_values("date").reset_index(drop=True)
    data["price"] = pd.to_numeric(data["price"], errors="coerce")
    data["volume"] = pd.to_numeric(data["volume"], errors="coerce")

    if len(data) < cfg.min_periods + 1:
        return []

    price_z = rolling_zscore(
        data["price"], cfg.window, cfg.min_periods, cfg.robust
    )
    volume_ratio = volume_spike_score(data["volume"], cfg.volume_window, cfg.min_periods)
    vol_ratio = volatility_regime_ratio(
        data["price"],
        cfg.volatility_short_window,
        cfg.volatility_long_window,
        min_periods=max(3, cfg.volatility_short_window - 2),
    )

    events: list[AnomalyEvent] = []

    for i in range(len(data)):
        timestamp = data.at[i, "date"].isoformat()
        price = float(data.at[i, "price"])

        # --- 1. price z-score ---
        z = price_z.iat[i]
        severity = classify_severity(z, cfg)
        if severity is not None:
            centre, _ = _baseline(data["price"], cfg.window, cfg.min_periods, cfg.robust)
            baseline = float(centre.iat[i]) if np.isfinite(centre.iat[i]) else price
            direction = "up" if z > 0 else "down"
            events.append(
                AnomalyEvent(
                    asset_id=asset_id,
                    symbol=symbol,
                    kind="price_zscore",
                    timestamp=timestamp,
                    severity=severity,
                    value=round(price, 8),
                    baseline=round(baseline, 8),
                    score=round(float(z), 4),
                    direction=direction,
                    detail=(
                        f"Price moved {abs(float(z)):.1f} standard deviations "
                        f"{direction} from its {cfg.window}-day baseline."
                    ),
                )
            )

        # --- 2. volume spike ---
        ratio = volume_ratio.iat[i]
        severity = _severity_from_ratio(ratio, cfg.volume_threshold)
        if severity is not None:
            prior = data["volume"].shift(1)
            base = prior.rolling(cfg.volume_window, min_periods=cfg.min_periods).mean()
            baseline = float(base.iat[i]) if np.isfinite(base.iat[i]) else float(data.at[i, "volume"])
            events.append(
                AnomalyEvent(
                    asset_id=asset_id,
                    symbol=symbol,
                    kind="volume_spike",
                    timestamp=timestamp,
                    severity=severity,
                    value=round(float(data.at[i, "volume"]), 2),
                    baseline=round(baseline, 2),
                    score=round(float(ratio), 4),
                    direction="up",
                    detail=(
                        f"Volume was {float(ratio):.1f}x its {cfg.volume_window}-day "
                        f"average."
                    ),
                )
            )

        # --- 3. volatility regime change ---
        ratio = vol_ratio.iat[i]
        severity = _severity_from_ratio(ratio, cfg.volatility_ratio_threshold)
        if severity is not None:
            events.append(
                AnomalyEvent(
                    asset_id=asset_id,
                    symbol=symbol,
                    kind="volatility_regime",
                    timestamp=timestamp,
                    severity=severity,
                    value=round(float(ratio), 4),
                    baseline=1.0,
                    score=round(float(ratio), 4),
                    direction="up",
                    detail=(
                        f"Realised volatility over {cfg.volatility_short_window} days "
                        f"was {float(ratio):.1f}x its {cfg.volatility_long_window}-day norm."
                    ),
                )
            )

    events.sort(key=lambda e: (e.timestamp, -SEVERITY_ORDER[e.severity]))
    return _apply_cooldown(events, cfg.cooldown)


def summarise(events: list[AnomalyEvent]) -> dict:
    """Count events by severity and by detector, for dashboards and digests."""
    by_severity = {"watch": 0, "notable": 0, "extreme": 0}
    by_kind: dict[str, int] = {}
    for event in events:
        by_severity[event.severity] += 1
        by_kind[event.kind] = by_kind.get(event.kind, 0) + 1
    return {
        "total": len(events),
        "by_severity": by_severity,
        "by_kind": by_kind,
    }

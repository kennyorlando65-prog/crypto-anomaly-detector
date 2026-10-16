"""Backtest: how many alerts would this have fired over the last N days?

WHY THIS EXISTS
---------------
An anomaly detector that only shows you today's flags is unfalsifiable. You
cannot tell whether it is finding real structure or just lighting up on noise.

The backtest replays the same detectors over a historical window and reports
what they would have produced. It is the honesty feature: it shows the false
positive rate instead of hiding it.

WHAT IT DOES NOT DO
-------------------
It does not measure profit, accuracy, or predictive power, because the
detectors make no prediction. There is no "signal quality" score here, and
inventing one would be dishonest. The output is a count of flags and their
severity mix, which is exactly what it claims to be.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.config import DetectorConfig
from engine.detectors import AnomalyEvent, detect_anomalies, summarise


@dataclass
class BacktestResult:
    """Aggregate result of replaying the detectors over a window."""

    asset_id: str
    symbol: str
    days: int
    observations: int
    total_events: int
    by_severity: dict
    by_kind: dict
    events_per_week: float
    events: list[AnomalyEvent]

    def to_dict(self, include_events: bool = True) -> dict:
        payload = {
            "asset_id": self.asset_id,
            "symbol": self.symbol,
            "days": self.days,
            "observations": self.observations,
            "total_events": self.total_events,
            "by_severity": self.by_severity,
            "by_kind": self.by_kind,
            "events_per_week": self.events_per_week,
        }
        if include_events:
            payload["events"] = [e.to_dict() for e in self.events]
        return payload


def run_backtest(
    frame: pd.DataFrame,
    asset_id: str,
    symbol: str,
    days: int = 90,
    cfg: DetectorConfig | None = None,
) -> BacktestResult:
    """Replay the detectors over the trailing ``days`` of a series.

    The window is sliced *before* detection, so the first scored day already
    has a full baseline behind it. Slicing after detection would let the
    detector see data from outside the window, which would flatter the count.
    """
    cfg = cfg or DetectorConfig()

    if frame is None or frame.empty:
        return BacktestResult(asset_id, symbol, days, 0, 0, {}, {}, 0.0, [])

    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], utc=True)
    data = data.sort_values("date").reset_index(drop=True)

    # Keep a warm-up margin so the first in-window day has a real baseline.
    warmup = max(cfg.window, cfg.volume_window, cfg.volatility_long_window)
    cutoff = data["date"].max() - pd.Timedelta(days=days)
    start = max(0, int((data["date"] < cutoff).sum()) - warmup)
    window = data.iloc[start:].reset_index(drop=True)

    events = detect_anomalies(window, asset_id, symbol, cfg)

    # Only count events that fall inside the requested window.
    in_window = [e for e in events if pd.Timestamp(e.timestamp) >= cutoff]
    stats = summarise(in_window)
    weeks = max(days / 7.0, 1e-9)

    return BacktestResult(
        asset_id=asset_id,
        symbol=symbol,
        days=days,
        observations=len(window),
        total_events=stats["total"],
        by_severity=stats["by_severity"],
        by_kind=stats["by_kind"],
        events_per_week=round(stats["total"] / weeks, 2),
        events=in_window,
    )

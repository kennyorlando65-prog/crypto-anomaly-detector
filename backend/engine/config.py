"""Configuration for the detection engine.

Every value here is a plain number a human chose. Nothing is learned, fitted,
or trained. The defaults are documented in the README with the reasoning
behind them, so a reader can disagree with a specific number and change it.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DetectorConfig:
    """Thresholds and windows for the three detectors.

    Attributes:
        window: Lookback length (in days) for the price z-score baseline.
        min_periods: Minimum observations before a baseline is considered valid.
        watch_threshold: Absolute z-score at which an event becomes ``watch``.
        notable_threshold: Absolute z-score at which an event becomes ``notable``.
        extreme_threshold: Absolute z-score at which an event becomes ``extreme``.
        volume_window: Lookback length (in days) for the volume baseline.
        volume_threshold: Ratio of current volume to baseline volume that fires.
        volatility_short_window: Recent window for realised volatility.
        volatility_long_window: Baseline window for realised volatility.
        volatility_ratio_threshold: Short/long volatility ratio that fires.
        robust: Use median/MAD instead of mean/standard deviation.
        cooldown: Days to suppress repeat events of the same kind on one asset.
    """

    # Rolling z-score on price
    window: int = 30
    min_periods: int = 10
    watch_threshold: float = 2.0
    notable_threshold: float = 3.0
    extreme_threshold: float = 4.0

    # Volume spike
    volume_window: int = 30
    volume_threshold: float = 2.5

    # Volatility regime change
    volatility_short_window: int = 7
    volatility_long_window: int = 30
    volatility_ratio_threshold: float = 2.0

    # Shared
    robust: bool = False
    cooldown: int = 3

    def to_dict(self) -> dict:
        """Return the config as a plain dict, for API responses."""
        return asdict(self)

    @classmethod
    def from_env(cls) -> DetectorConfig:
        """Build a config from environment variables, falling back to defaults.

        Only the values worth tuning per-deployment are read from the
        environment. Everything else keeps its default.
        """

        def _int(name: str, default: int) -> int:
            raw = os.environ.get(name, "").strip()
            if not raw:
                return default
            try:
                return int(raw)
            except ValueError:
                return default

        def _float(name: str, default: float) -> float:
            raw = os.environ.get(name, "").strip()
            if not raw:
                return default
            try:
                return float(raw)
            except ValueError:
                return default

        def _bool(name: str, default: bool) -> bool:
            raw = os.environ.get(name, "").strip().lower()
            if not raw:
                return default
            return raw in {"1", "true", "yes", "on"}

        return cls(
            window=_int("DETECTOR_WINDOW", cls.window),
            min_periods=_int("DETECTOR_MIN_PERIODS", cls.min_periods),
            watch_threshold=_float("DETECTOR_WATCH_THRESHOLD", cls.watch_threshold),
            notable_threshold=_float("DETECTOR_NOTABLE_THRESHOLD", cls.notable_threshold),
            extreme_threshold=_float("DETECTOR_EXTREME_THRESHOLD", cls.extreme_threshold),
            volume_window=_int("DETECTOR_VOLUME_WINDOW", cls.volume_window),
            volume_threshold=_float("DETECTOR_VOLUME_THRESHOLD", cls.volume_threshold),
            volatility_short_window=_int(
                "DETECTOR_VOLATILITY_SHORT_WINDOW", cls.volatility_short_window
            ),
            volatility_long_window=_int(
                "DETECTOR_VOLATILITY_LONG_WINDOW", cls.volatility_long_window
            ),
            volatility_ratio_threshold=_float(
                "DETECTOR_VOLATILITY_RATIO_THRESHOLD", cls.volatility_ratio_threshold
            ),
            robust=_bool("DETECTOR_ROBUST", cls.robust),
            cooldown=_int("DETECTOR_COOLDOWN", cls.cooldown),
        )

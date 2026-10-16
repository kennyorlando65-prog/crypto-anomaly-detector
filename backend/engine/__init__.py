"""Statistical anomaly detection engine for crypto market data.

This package is deliberately plain: pandas, numpy, and classical statistics.
No machine learning, no trained models, no price prediction.
"""

from engine.config import DetectorConfig
from engine.detectors import (
    AnomalyEvent,
    classify_severity,
    detect_anomalies,
    rolling_zscore,
    volatility_regime_ratio,
    volume_spike_score,
)

__all__ = [
    "DetectorConfig",
    "AnomalyEvent",
    "classify_severity",
    "detect_anomalies",
    "rolling_zscore",
    "volume_spike_score",
    "volatility_regime_ratio",
]

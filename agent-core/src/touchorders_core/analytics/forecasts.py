"""Deterministic EWMA and weekday-seasonality forecasts."""

from __future__ import annotations

from collections.abc import Sequence


def ewma(values: Sequence[float], alpha: float = 0.35) -> float:
    if not values:
        return 0.0
    estimate = float(values[0])
    for value in values[1:]:
        estimate = alpha * float(value) + (1 - alpha) * estimate
    return estimate


def weekday_seasonal_forecast(values: Sequence[float], weekday_factor: float = 1.0, alpha: float = 0.35) -> float:
    """Forecast with a bounded seasonality adjustment; never invokes an LLM."""

    return max(0.0, ewma(values, alpha) * max(0.0, weekday_factor))

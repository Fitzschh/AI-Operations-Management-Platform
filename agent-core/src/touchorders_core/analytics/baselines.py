"""Trailing same-hour-of-week baseline generation."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import mean

from touchorders_core.datastore.repositories import AnalyticsRepository


def trimmed_mean(values: Sequence[float], proportion: float = 0.1) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    trim = int(len(ordered) * proportion)
    retained = ordered[trim:len(ordered) - trim] if len(ordered) - 2 * trim > 0 else ordered
    return mean(retained)


class BaselineGenerator:
    def __init__(self, repository: AnalyticsRepository, min_baseline_samples: int = 3) -> None:
        self._repository = repository
        self.min_baseline_samples = min_baseline_samples

    def store(self, *, tenant_id: str, metric_id: str, entity_id: str, hour_of_week: int, samples: Sequence[float]) -> None:
        self._repository.upsert_baseline(tenant_id=tenant_id, metric_id=metric_id, entity_id=entity_id, hour_of_week=hour_of_week, mean=mean(samples) if samples else 0.0, trimmed_mean=trimmed_mean(samples), sample_count=len(samples))

    def eligible(self, *, tenant_id: str, metric_id: str, entity_id: str, hour_of_week: int) -> float | None:
        baseline = self._repository.baseline(metric_id, entity_id, hour_of_week, tenant_id)
        if baseline is None or baseline[1] < self.min_baseline_samples:
            return None
        return baseline[0]

"""Generic POS webhook adapter delegating all semantics to the normalizer."""

from __future__ import annotations

from typing import Any

from touchorders_core.ingestion.normalizer import Normalizer


class WebhookAdapter:
    def __init__(self, normalizer: Normalizer) -> None:
        self._normalizer = normalizer

    def ingest(self, kind: str, payload: dict[str, Any], tenant_id: str = "default") -> object:
        handlers = {"inventory": self._normalizer.inventory, "order": self._normalizer.order, "ticket": self._normalizer.ticket}
        try:
            return handlers[kind](payload, tenant_id)
        except KeyError as exc:
            raise ValueError(f"Unsupported webhook kind: {kind}") from exc

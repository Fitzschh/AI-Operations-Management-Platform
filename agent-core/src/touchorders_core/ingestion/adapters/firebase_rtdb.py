"""Firebase RTDB seam; credentials and listener transport stay outside normalization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class FirebaseRTDBAdapter:
    """Adapter callback used by the Stage 2 Firebase listener integration.

    The adapter purposefully does not import a Firebase SDK. An application composition root
    supplies its listener and forwards payloads to this tested normalization seam.
    """

    def __init__(self, on_inventory: Callable[[dict[str, Any]], object], on_order: Callable[[dict[str, Any]], object]) -> None:
        self._on_inventory = on_inventory
        self._on_order = on_order

    def handle(self, path: str, payload: dict[str, Any]) -> object:
        if path.startswith("/inventory"):
            return self._on_inventory(payload)
        if path.startswith("/orders"):
            return self._on_order(payload)
        raise ValueError(f"Unsupported Firebase RTDB path: {path}")

"""Append-only hash-chained audit writer; audit failures fail the audited action."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from touchorders_core.datastore.orm import AuditLogRow
from touchorders_core.datastore.repositories import AuditRepository
from touchorders_core.domain.common import utc_now


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


class AuditLogger:
    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    def write(self, *, actor: str, action: str, entity_type: str, entity_id: str, payload: dict[str, Any], correlation_id: str | None = None) -> str:
        previous = self._repository.last()
        at = utc_now()
        payload_hash = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        next_seq = (previous.seq + 1) if previous else 1
        previous_hash = previous.record_hash if previous else None
        material = f"{previous_hash or ''}|{payload_hash}|{next_seq}|{at.isoformat()}".encode()
        record_hash = hashlib.sha256(material).hexdigest()
        self._repository.append(AuditLogRow(at=at, actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, correlation_id=correlation_id, payload=payload, payload_hash=payload_hash, prev_hash=previous_hash, record_hash=record_hash))
        return record_hash

    def verify(self) -> bool:
        previous_hash: str | None = None
        for record in self._repository.entries():
            if record.prev_hash != previous_hash:
                return False
            payload_hash = hashlib.sha256(canonical_json(record.payload).encode()).hexdigest()
            expected = hashlib.sha256(f"{previous_hash or ''}|{payload_hash}|{record.seq}|{record.at.isoformat()}".encode()).hexdigest()
            if record.payload_hash != payload_hash or record.record_hash != expected:
                return False
            previous_hash = record.record_hash
        return True

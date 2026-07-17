"""§10.4 append-only hash chain: tamper-evident and fail-closed."""

from __future__ import annotations

import pytest

from touchorders_core.datastore.orm import AuditLogRow
from touchorders_core.observability.audit import AuditLogger


def _write_three(audit: AuditLogger) -> None:
    audit.write(actor="system:test", action="event.certified", entity_type="event", entity_id="e1", payload={"a": 1})
    audit.write(actor="agent:realtime_analyst", action="agent.invoked", entity_type="incident", entity_id="i1", payload={"b": 2})
    audit.write(actor="human:mgr", action="approval.decided", entity_type="approval", entity_id="ap1", payload={"decision": "APPROVE"})


def test_chain_verifies_and_links(repos) -> None:
    _write_three(repos.audit)
    assert repos.audit.verify() is True
    rows = repos.audit_repo.entries()
    assert [r.seq for r in rows] == [1, 2, 3]
    assert rows[0].prev_hash is None
    assert rows[1].prev_hash == rows[0].record_hash
    assert rows[2].prev_hash == rows[1].record_hash


def test_tampering_breaks_the_chain(repos) -> None:
    _write_three(repos.audit)
    with repos.factory() as session:
        row = session.get(AuditLogRow, 2)
        row.payload = {"b": 999}  # rewrite a committed payload
        session.commit()
    assert repos.audit.verify() is False


def test_audit_is_fail_closed(repos) -> None:
    """If the audit insert cannot commit, write() must raise so the audited action fails (P7)."""

    class BrokenAuditRepo:
        def last(self):
            return None

        def append(self, row: AuditLogRow) -> None:
            raise RuntimeError("disk full")

    logger = AuditLogger(BrokenAuditRepo())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        logger.write(actor="system:test", action="tool.executed", entity_type="tool", entity_id="t1", payload={})

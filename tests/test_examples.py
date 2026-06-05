"""Smoke test for the runnable examples (keeps examples/ covered + working)."""

from __future__ import annotations

from examples.quickstart_um_timeliness import run
from payer_agent_audit.schemas.audit_event import AuditEventType


def test_quickstart_runs_and_chain_verifies():
    chain = run()
    assert chain.verify() is True
    types = {e.event_type for e in chain._events}
    assert AuditEventType.UM_TIMELINESS_CHECKED in types
    assert AuditEventType.CLINICIAN_OF_RECORD_ATTESTED in types
    assert AuditEventType.ADVERSE_BENEFIT_DETERMINATION in types
    assert AuditEventType.EXTERNAL_REVIEW_ROUTED in types

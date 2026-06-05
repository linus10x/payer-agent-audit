"""Canonical schemas for payer-agent-audit."""

from __future__ import annotations

from typing import Any

from payer_agent_audit.schemas.audit_event import (
    AuditEvent,
    AuditEventType,
    AutonomyLevel,
)

__all__ = ["AuditChain", "AuditEvent", "AuditEventType", "AutonomyLevel"]  # noqa: F822


def __getattr__(name: str) -> Any:
    if name == "AuditChain":
        from payer_agent_audit.governance.audit_chain import AuditChain

        return AuditChain
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

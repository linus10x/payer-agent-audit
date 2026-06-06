"""Governance patterns for autonomous AI agents in health-insurance / payer
operations (NAIC umbrella).

These are reference IP for adoption — documented, tested patterns — NOT a
deployed control operating in production. The deployer's substrate is the
production deployment. See LIMITATIONS.md and DISCLAIMER.md.

This library makes NO medical-necessity or clinical determination. A payer
coverage decision is a benefit adjudication under insurance law (NAIC /
state DOI / ERISA 29 CFR 2560.503-1 / CMS / ACA 45 CFR 147.136), distinct
from FDA Software-as-a-Medical-Device regulation. See the payer-not-FDA-SaMD
boundary in LIMITATIONS.md.

The headline primitives and controls are re-exported here for convenience::

    from payer_agent_audit import AuditChain, SovereignVeto, DEFCONMachine
    from payer_agent_audit import UMTimelinessControl, FundingType
"""

from __future__ import annotations

from payer_agent_audit.governance import (
    DEFCON,
    AuditChain,
    DEFCONMachine,
    EffectiveChallengeHarness,
    SovereignVeto,
    check_a2_to_a3_promotion,
)
from payer_agent_audit.payer import (
    AppealIROControl,
    ClinicianOfRecordControl,
    FundingType,
    RequestCategory,
    UMTimelinessControl,
    obligations_for,
)
from payer_agent_audit.schemas import (
    AuditEvent,
    AuditEventType,
    AutonomyLevel,
)

__version__ = "0.1.1"

__all__ = [
    "AppealIROControl",
    "AuditChain",
    "AuditEvent",
    "AuditEventType",
    "AutonomyLevel",
    "ClinicianOfRecordControl",
    "DEFCON",
    "DEFCONMachine",
    "EffectiveChallengeHarness",
    "FundingType",
    "RequestCategory",
    "SovereignVeto",
    "UMTimelinessControl",
    "__version__",
    "check_a2_to_a3_promotion",
    "obligations_for",
]

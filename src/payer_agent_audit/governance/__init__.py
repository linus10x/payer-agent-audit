"""Governance primitives for payer-agent-audit.

The five corrected-spec primitives:
    P1  AutonomyLadder level-gate (autonomy_ladder.py)
    P2  SovereignVeto             (sovereign_veto.py)
    P3  AuditChain                (audit_chain.py)
    P4  DEFCONMachine             (defcon.py)
    P5  EffectiveChallengeHarness (effective_challenge_harness.py)
"""

from __future__ import annotations

from payer_agent_audit.governance.audit_chain import AuditChain, AuditChainTamperError
from payer_agent_audit.governance.autonomy_ladder import (
    ADVISORY,
    Attestation,
    PromotionEvidence,
    PromotionGateNotMet,
    PromotionGateReport,
    check_a2_to_a3_promotion,
)
from payer_agent_audit.governance.defcon import (
    DEFCON,
    DEFCONMachine,
    DEFCONOverrideRejectedError,
    RiskMetrics,
)
from payer_agent_audit.governance.effective_challenge_harness import (
    ChallengeReport,
    ChallengerNotIndependentError,
    EffectiveChallengeHarness,
    IndependenceAttestation,
)
from payer_agent_audit.governance.sovereign_veto import (
    Authorizer,
    SovereignVeto,
    VetoBlockedError,
    VetoReason,
    VetoRecord,
)
from payer_agent_audit.governance.witness_anchor import (
    InMemoryWitness,
    RekorWitness,
    WitnessReceipt,
    WitnessRegister,
)

__all__ = [
    "ADVISORY",
    "Attestation",
    "AuditChain",
    "AuditChainTamperError",
    "Authorizer",
    "ChallengeReport",
    "ChallengerNotIndependentError",
    "DEFCON",
    "DEFCONMachine",
    "DEFCONOverrideRejectedError",
    "EffectiveChallengeHarness",
    "InMemoryWitness",
    "IndependenceAttestation",
    "PromotionEvidence",
    "PromotionGateNotMet",
    "PromotionGateReport",
    "RekorWitness",
    "RiskMetrics",
    "SovereignVeto",
    "VetoBlockedError",
    "VetoReason",
    "VetoRecord",
    "WitnessReceipt",
    "WitnessRegister",
    "check_a2_to_a3_promotion",
]

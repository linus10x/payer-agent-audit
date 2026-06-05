"""
Audit Event Schema — Tamper-Detecting Hash-Chain Logging (within-trust-boundary)
================================================================================

Defines the canonical schema for audit events emitted by autonomous AI agents
operating in health-insurance / payer workflows (utilization management, prior
authorization, claims adjudication support, appeals routing). Each event is
chained to the previous via SHA-256, making any retroactive tampering detectable
during verification *within the trust boundary that produced the chain*.

For external tamper-EVIDENCE (cryptographic anchoring to a third-party witness
register such as Sigstore Rekor or OpenTimestamps), see
``payer_agent_audit.governance.witness_anchor``.

Boundary note (payer-not-FDA-SaMD): the events below record *governance and
benefit-adjudication* actions — they do not assert, and this library makes no
claim about, medical necessity or any clinical determination. A payer coverage
decision is a benefit adjudication under insurance law (NAIC / state DOI /
ERISA 29 CFR 2560.503-1 / CMS / ACA 45 CFR 147.136), not an FDA-regulated
medical device. See ``LIMITATIONS.md``.

Design principles:
    - Every agent action that changes governance state produces an audit event
    - Events are append-only — never mutated after creation
    - Hash chain: event_hash = SHA-256(event fields + prev_hash)
    - Verifier can replay the chain and detect any inserted/modified event
    - Schema is intentionally minimal — extend per your compliance requirements
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class AuditEventType(Enum):
    """Classification of audit events by category."""

    # Agent lifecycle
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_ERROR = "agent.error"

    # Decision events
    DECISION_MADE = "decision.made"
    DECISION_VETOED = "decision.vetoed"
    DECISION_OVERRIDDEN = "decision.overridden"

    # Risk events
    RISK_ESCALATION = "risk.escalation"
    RISK_DEESCALATION = "risk.deescalation"
    HALT_TRIGGERED = "risk.halt"

    # Human-in-the-loop
    HUMAN_APPROVED = "human.approved"
    HUMAN_REJECTED = "human.rejected"
    HUMAN_OVERRIDE = "human.override"

    # Governance
    VETO_APPLIED = "governance.veto"
    POLICY_VIOLATION = "governance.policy_violation"
    COMPLIANCE_CHECK = "governance.compliance_check"
    PROMOTION_GATE_EVALUATED = "governance.promotion_gate_evaluated"

    # Vendor-mediated AI
    VENDOR_SCORE_RECORDED = "vendor.score_recorded"
    VENDOR_SCORE_DRIFT_DETECTED = "vendor.score_drift_detected"

    # External anchoring
    WITNESS_ANCHOR = "audit_chain.witness_anchor"

    # Model governance
    MODEL_VALIDATED = "model.validated"  # effective-challenge attestation (P5)

    # Payer-specific (module a — health-payer; NAIC umbrella)
    #
    # These record the GOVERNANCE of a benefit-adjudication workflow — the
    # presence/absence of a timely decision, a clinician-of-record on a denial,
    # and an appeal/IRO pathway. They do NOT encode a medical-necessity or
    # clinical determination (see module docstring boundary note).
    COVERAGE_DETERMINATION = "payer.coverage_determination"  # NAIC / state DOI
    PRIOR_AUTH_DECISION = "payer.prior_auth_decision"  # CMS-0057-F UM timeliness
    UM_TIMELINESS_CHECKED = "payer.um_timeliness_checked"  # CMS / ERISA / ACA
    CLINICIAN_OF_RECORD_ATTESTED = "payer.clinician_of_record_attested"  # denial review
    ADVERSE_BENEFIT_DETERMINATION = "payer.adverse_benefit_determination"  # ERISA 2560.503-1
    APPEAL_FILED = "payer.appeal_filed"  # internal appeal
    EXTERNAL_REVIEW_ROUTED = "payer.external_review_routed"  # ACA 147.136 IRO


class AutonomyLevel(Enum):
    """
    Autonomy classification per the A0->A4 ladder.
    Maps to human oversight requirements at each level.
    """

    A0 = "A0"  # Informational — agent reads and recommends, no write authority
    A1 = "A1"  # Assisted — agent drafts, human approves every write
    A2 = "A2"  # Delegated — agent writes in a hard envelope, sampled review
    A3 = "A3"  # Supervised Autonomous — in-scope autonomous writes, sovereign veto, live ledger
    A4 = "A4"  # Production Autonomous — A3 plus orchestration and operator-validated escalation


@dataclass(frozen=True)
class AuditEvent:
    """
    Immutable audit record. Hash is computed on construction.

    The dataclass is ``frozen=True`` — every field is read-only
    post-construction. Two construction paths exist:

      * ``AuditEvent.create(...)`` — for *new* events. Computes the
        hash from the field values and freezes the result.

      * ``AuditEvent.from_jsonl(dict)`` — for *replay* of stored events.
        Reconstructs with the stored ``event_hash``, recomputes against
        the reconstructed fields, and raises ``AuditChainTamperError`` on
        mismatch. The chain is self-verifying on load, not just on
        explicit ``verify()``.

    The bare ``AuditEvent(...)`` constructor still works — if no
    ``event_hash`` keyword is supplied, the constructor computes one.
    Replay code that passes a stored ``event_hash`` MUST instead call
    ``from_jsonl`` so the recomputation gate fires.

    Fields:
        event_id:       UUID4 uniquely identifying this event
        event_type:     Classification from AuditEventType
        autonomy_level: A0->A4 level at which this decision was made
        agent_id:       Identifier of the agent that generated this event
        timestamp:      UTC ISO-8601 timestamp
        payload:        Arbitrary event-specific data (keep minimal)
        actor_id:       Human/principal actor if applicable
        prev_hash:      SHA-256 hash of the previous event (genesis seed)
        event_hash:     SHA-256 hash of this event + prev_hash (computed)
        schema_version: Schema version for forward compatibility
    """

    event_type: AuditEventType
    autonomy_level: AutonomyLevel
    agent_id: str
    payload: dict[str, Any]
    prev_hash: str

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    actor_id: str | None = None
    schema_version: str = "1.0.0"
    event_hash: str = ""

    def __post_init__(self) -> None:
        if not self.event_hash:
            object.__setattr__(self, "event_hash", self._compute_hash())

    @classmethod
    def create(
        cls,
        *,
        event_type: AuditEventType,
        autonomy_level: AutonomyLevel,
        agent_id: str,
        payload: dict[str, Any],
        prev_hash: str,
        event_id: str | None = None,
        timestamp: str | None = None,
        actor_id: str | None = None,
        schema_version: str = "1.0.0",
    ) -> AuditEvent:
        """Construct a *new* event. Computes ``event_hash`` and freezes."""
        kwargs: dict[str, Any] = {
            "event_type": event_type,
            "autonomy_level": autonomy_level,
            "agent_id": agent_id,
            "payload": payload,
            "prev_hash": prev_hash,
            "actor_id": actor_id,
            "schema_version": schema_version,
        }
        if event_id is not None:
            kwargs["event_id"] = event_id
        if timestamp is not None:
            kwargs["timestamp"] = timestamp
        return cls(**kwargs)

    @classmethod
    def from_jsonl(cls, data: dict[str, Any]) -> AuditEvent:
        """Replay a stored event. Recomputes and raises on mismatch."""
        # Lazy import — ``audit_chain`` imports this module at load time,
        # so the reverse import stays lazy to avoid a circular import.
        from payer_agent_audit.governance.audit_chain import AuditChainTamperError

        stored_event_hash = str(data["event_hash"])
        event = cls(
            event_type=AuditEventType(data["event_type"]),
            autonomy_level=AutonomyLevel(data["autonomy_level"]),
            agent_id=str(data["agent_id"]),
            payload=dict(data["payload"]),
            prev_hash=str(data["prev_hash"]),
            event_id=str(data["event_id"]),
            timestamp=str(data["timestamp"]),
            actor_id=None if data.get("actor_id") is None else str(data["actor_id"]),
            schema_version=str(data.get("schema_version", "1.0.0")),
            event_hash=stored_event_hash,
        )
        recomputed = event._compute_hash()
        if recomputed != stored_event_hash:
            raise AuditChainTamperError(
                f"event_hash mismatch on replay (event_id={event.event_id!r}): "
                f"stored={stored_event_hash!r}, recomputed={recomputed!r} — "
                "the on-disk line has been modified after writing"
            )
        return event

    def _compute_hash(self) -> str:
        payload = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "autonomy_level": self.autonomy_level.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "actor_id": self.actor_id,
            "prev_hash": self.prev_hash,
            "schema_version": self.schema_version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "autonomy_level": self.autonomy_level.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "actor_id": self.actor_id,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
            "schema_version": self.schema_version,
        }

    def to_jsonl(self) -> str:
        """Single JSONL line for append-only log files."""
        return json.dumps(self.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------- #
# Backward-compat re-export                                              #
# ---------------------------------------------------------------------- #
# ``AuditChain`` lives in governance/audit_chain.py so it can consume the
# witness register. Re-exported here lazily via module __getattr__ to
# avoid a circular import when the governance package is loaded first.


def __getattr__(name: str) -> Any:
    if name == "AuditChain":
        from payer_agent_audit.governance.audit_chain import AuditChain

        return AuditChain
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["AuditChain", "AuditEvent", "AuditEventType", "AutonomyLevel"]  # noqa: F822  # AuditChain resolved via __getattr__

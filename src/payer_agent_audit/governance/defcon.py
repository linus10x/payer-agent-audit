"""DEFCON Risk-State Machine (P4) — graduated autonomy throttle.

Escalation is automatic and immediate; de-escalation is deliberately
hard. The machine moves an autonomous agent through risk states
(NORMAL -> CAUTION -> ALERT -> DANGER -> HALT -> SHUTDOWN) as risk
metrics breach thresholds. In a payer workflow the metrics are
operational-risk signals (e.g. denial-rate spike, UM-timeliness breach
rate, appeal-overturn rate) — NOT a clinical determination.

P4 corrected-spec properties (the bar this is built to):
  * A **transition-direction guard**: no actor can move
    ``HALT``/``SHUTDOWN`` -> ``NORMAL`` in one unguarded call.
    De-escalation must step DOWN one level at a time and each step
    requires the manual-override + Authorizer path.
  * The Authorizer is **mandatory in production mode** (fail-closed
    construction without one).

Escalation (moving to a HIGHER state) is always allowed in a single
call — you never want to slow down a halt. The guard applies only to
DE-escalation.

The default constructor (``production=False``) preserves a backward-
compatible advisory contract and is labeled advisory.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from payer_agent_audit.governance.sovereign_veto import Authorizer
from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

if TYPE_CHECKING:
    from payer_agent_audit.governance.audit_chain import AuditChain


class DEFCON(IntEnum):
    """Risk states, ascending in severity. Integer values enable ordering."""

    NORMAL = 1
    CAUTION = 2
    ALERT = 3
    DANGER = 4
    HALT = 5
    SHUTDOWN = 6


# States from which a single-call jump to NORMAL is forbidden — recovery
# from a hard stop must be stepwise and human-authorized at each step.
_HARD_STOP_STATES = frozenset({DEFCON.HALT, DEFCON.SHUTDOWN})


@dataclass(frozen=True)
class RiskMetrics:
    """Operational-risk inputs the machine evaluates. Domain-agnostic.

    Frozen — a pure input value object; a caller must not be able to mutate a
    metrics instance mid-evaluation.
    """

    breach_rate: float = 0.0  # e.g. UM-timeliness breaches / decisions
    anomaly_score: float = 0.0  # 0..1 anomaly detector output
    consecutive_failures: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class DEFCONOverrideRejectedError(RuntimeError):
    """Raised when a manual override violates the transition-direction guard
    or is not authorized."""


class DEFCONMachine:
    """Graduated autonomy throttle with a hardened de-escalation path (P4)."""

    # Escalation thresholds (illustrative; deployers tune to their risk
    # surface). Higher metric -> higher DEFCON.
    BREACH_RATE_SHUTDOWN = 0.40
    BREACH_RATE_HALT = 0.30
    BREACH_RATE_DANGER = 0.20
    BREACH_RATE_ALERT = 0.10
    BREACH_RATE_CAUTION = 0.05
    ANOMALY_HALT = 0.95
    ANOMALY_DANGER = 0.85
    CONSECUTIVE_FAILURES_DANGER = 6
    CONSECUTIVE_FAILURES_ALERT = 4

    def __init__(
        self,
        authorizer: Authorizer | None = None,
        production: bool = False,
        *,
        audit_chain: AuditChain | None = None,
        agent_id: str = "defcon-machine",
    ) -> None:
        self._level = DEFCON.NORMAL
        self._authorizer = authorizer
        self._production = production
        self._audit_chain = audit_chain
        self._agent_id = agent_id
        self._history: list[dict[str, Any]] = []

        if production and authorizer is None:
            raise ValueError(
                "DEFCONMachine(production=True) requires an authorizer so a "
                "manual de-escalation is bound to an authenticated principal. "
                "Refusing to start fail-closed."
            )
        if not production and authorizer is None:
            warnings.warn(
                "DEFCONMachine constructed without an authorizer (advisory mode): "
                "manual_override de-escalations are not authenticated. Pass "
                "production=True with an authorizer to enforce.",
                stacklevel=2,
            )

    @property
    def level(self) -> DEFCON:
        return self._level

    def _compute_target(self, metrics: RiskMetrics) -> DEFCON:
        """Map metrics to the escalation target (never de-escalates)."""
        if metrics.breach_rate >= self.BREACH_RATE_SHUTDOWN:
            return DEFCON.SHUTDOWN
        if (
            metrics.breach_rate >= self.BREACH_RATE_HALT
            or metrics.anomaly_score >= self.ANOMALY_HALT
        ):
            return DEFCON.HALT
        if (
            metrics.breach_rate >= self.BREACH_RATE_DANGER
            or metrics.anomaly_score >= self.ANOMALY_DANGER
            or metrics.consecutive_failures >= self.CONSECUTIVE_FAILURES_DANGER
        ):
            return DEFCON.DANGER
        if (
            metrics.breach_rate >= self.BREACH_RATE_ALERT
            or metrics.consecutive_failures >= self.CONSECUTIVE_FAILURES_ALERT
        ):
            return DEFCON.ALERT
        if metrics.breach_rate >= self.BREACH_RATE_CAUTION:
            return DEFCON.CAUTION
        return DEFCON.NORMAL

    def evaluate(self, metrics: RiskMetrics) -> DEFCON:
        """Escalate (only) based on metrics. Never auto-de-escalates.

        Escalation is immediate. The machine NEVER lowers its own state
        from metrics — coming down requires ``manual_override`` so a human
        is on the hook for resuming autonomy. This is why a transient
        metric dip cannot silently re-arm a halted agent.
        """
        target = self._compute_target(metrics)
        if target > self._level:
            self._record_transition(self._level, target, "evaluate", None, metrics)
            self._level = target
        return self._level

    def manual_override(
        self,
        target: DEFCON,
        operator_id: str,
        reason: str,
        metrics: RiskMetrics | None = None,
    ) -> DEFCON:
        """Operator-driven transition with the direction guard enforced.

        Rules:
          * Escalation (``target`` > current) is always allowed.
          * De-escalation from a hard-stop state (HALT/SHUTDOWN) may move
            **at most one level down** per call — a single-call jump to
            NORMAL is rejected. This forces a deliberate, stepwise,
            re-authorized recovery.
          * De-escalation from any state may not skip more than one level.
          * In production mode the Authorizer must vouch for the operator.
        """
        current = self._level

        # Authenticated-principal binding (mandatory in production).
        if self._authorizer is not None:
            context = {
                "from": current.name,
                "to": target.name,
                "reason": reason,
            }
            if not self._authorizer.authorize(operator_id, "defcon_override", context):
                raise DEFCONOverrideRejectedError(
                    f"operator_id {operator_id!r} not authorized for DEFCON override"
                )

        if target == current:
            return self._level

        # Escalation is always permitted in a single call.
        if target > current:
            self._record_transition(current, target, "manual_override", operator_id, metrics)
            self._level = target
            return self._level

        # De-escalation — enforce the transition-direction guard.
        if current in _HARD_STOP_STATES and target == DEFCON.NORMAL:
            raise DEFCONOverrideRejectedError(
                f"transition-direction guard: cannot move {current.name} -> NORMAL "
                f"in one call. Recovery from a hard stop must step down one level "
                f"at a time, each step re-authorized. Move {current.name} -> "
                f"{DEFCON(current - 1).name} first."
            )
        if (current - target) > 1:
            raise DEFCONOverrideRejectedError(
                f"transition-direction guard: de-escalation may step down only one "
                f"level per call (requested {current.name} -> {target.name}). "
                f"Step to {DEFCON(current - 1).name} first."
            )

        self._record_transition(current, target, "manual_override", operator_id, metrics)
        self._level = target
        return self._level

    def _record_transition(
        self,
        from_state: DEFCON,
        to_state: DEFCON,
        actor: str,
        operator_id: str | None,
        metrics: RiskMetrics | None,
    ) -> None:
        metrics_payload = (
            None
            if metrics is None
            else {
                "breach_rate": metrics.breach_rate,
                "anomaly_score": metrics.anomaly_score,
                "consecutive_failures": metrics.consecutive_failures,
            }
        )
        record = {
            "from": from_state.name,
            "to": to_state.name,
            "actor": actor,
            "operator_id": operator_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": metrics_payload,
        }
        self._history.append(record)

        # Chain the transition so DEFCON participates in the audit ledger like
        # the other primitives (the "every governance event is chained" thesis).
        if self._audit_chain is not None:
            if to_state >= DEFCON.HALT:
                event_type = AuditEventType.HALT_TRIGGERED
            elif to_state > from_state:
                event_type = AuditEventType.RISK_ESCALATION
            else:
                event_type = AuditEventType.RISK_DEESCALATION
            self._audit_chain.append(
                event_type=event_type,
                autonomy_level=AutonomyLevel.A3,
                agent_id=self._agent_id,
                payload=record,
                actor_id=operator_id,
            )

    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

"""Autonomy Ladder Level-Gate (P1) — A0->A4 promotion gate.

The Autonomy Ladder classifies an agent's write authority from A0
(read-only / informational) to A4 (production autonomous). Promotion to a
higher level is gated: an agent may not be promoted until the controls
required at the *lower* level are demonstrably in place.

P1 corrected-spec properties (the bar this is built to):
  * The gate REFUSES promotion when lower-level controls are unmet.
  * It requires **independent attestation** of its inputs — it does not
    simply trust caller-asserted booleans. Each requirement is an
    ``Attestation`` object naming WHO attested, WHEN, and an evidence
    reference; an attestation whose attester is the agent itself
    (self-attestation) is rejected, and a stale or unsigned attestation
    does not satisfy the gate.
  * The gate is **advisory by nature and LABELED advisory**: it codifies
    the *check*, not the evidence. It tells a deployer whether the
    attested record satisfies the promotion criteria; it does not itself
    run the load test or validate the attester's identity end-to-end —
    binding the attester to a real principal is the deployer's IdP
    responsibility. This label is explicit so no one mistakes the gate
    for an enforcing control.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from payer_agent_audit.schemas.audit_event import AutonomyLevel

# This gate is ADVISORY. It evaluates an attested evidence record against
# the promotion criteria; it does not itself enforce promotion or validate
# the attester's identity end-to-end. See module docstring + LIMITATIONS.md.
ADVISORY: bool = True

_MIN_AUDIT_LEDGER_DAYS = 90
_MIN_SHADOW_MODE_DAYS = 30
# An attestation older than this is stale and does not satisfy the gate.
_MAX_ATTESTATION_AGE_DAYS = 180


class PromotionGateNotMet(RuntimeError):  # noqa: N818  # deliberate domain name
    """Raised by ``PromotionGateReport.raise_if_blocked`` when blocked."""


@dataclass(frozen=True)
class Attestation:
    """An independently-attested fact about a control's state.

    ``attester_id`` MUST be a principal distinct from the agent being
    promoted (no self-attestation). ``attested_at`` is an ISO-8601 UTC
    timestamp; a stale attestation does not satisfy the gate.
    ``evidence_ref`` points at the artifact (load-test report, ledger
    export, etc.) a reviewer can independently inspect.
    """

    claim: str
    attester_id: str
    attested_at: str
    evidence_ref: str
    value: bool = True

    def is_valid(self, *, agent_id: str, now: datetime | None = None) -> tuple[bool, str]:
        """Return ``(ok, reason)``. Rejects self-attestation, missing
        evidence, stale timestamps, and a false/withheld claim.

        Identity comparison is normalized (strip + casefold) so a trivial
        whitespace/case variation of the agent id cannot defeat the
        self-attestation guard, and a blank-after-strip attester is rejected.
        """
        attester_norm = self.attester_id.strip().casefold()
        if not attester_norm:
            return False, f"{self.claim}: attester_id is empty/blank (no independent attester)"
        if attester_norm == agent_id.strip().casefold():
            return False, (
                f"{self.claim}: self-attestation rejected — attester_id "
                f"{self.attester_id!r} resolves to the agent being promoted"
            )
        if not self.evidence_ref:
            return False, f"{self.claim}: no evidence_ref supplied"
        if not self.value:
            return False, f"{self.claim}: attested value is False/withheld"
        try:
            ts = datetime.fromisoformat(self.attested_at)
        except (ValueError, TypeError):
            return False, f"{self.claim}: attested_at {self.attested_at!r} is not ISO-8601"
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        age = current - ts
        if age > timedelta(days=_MAX_ATTESTATION_AGE_DAYS):
            return False, (
                f"{self.claim}: attestation is stale ({age.days}d > {_MAX_ATTESTATION_AGE_DAYS}d)"
            )
        if age < timedelta(0):
            return False, f"{self.claim}: attested_at is in the future"
        return True, "ok"


@dataclass(frozen=True)
class PromotionEvidence:
    """The attested evidence record for an A2->A3 promotion.

    Each field is an ``Attestation`` — NOT a bare bool. This is the
    corrected-spec departure from a gate that trusts caller-asserted
    booleans: the gate evaluates attested objects with an independent
    attester, evidence reference, and freshness.
    """

    sovereign_veto_load_tested: Attestation
    audit_ledger_running_for: timedelta
    audit_ledger_running_attestation: Attestation
    shadow_mode_running_for: timedelta
    shadow_mode_attestation: Attestation
    circuit_breaker_test_recent: Attestation


@dataclass(frozen=True)
class PromotionGateReport:
    """Outcome of a promotion-gate evaluation."""

    passed: bool
    failures: tuple[str, ...]
    advisory: bool = ADVISORY

    def raise_if_blocked(self) -> None:
        if not self.passed:
            raise PromotionGateNotMet(
                "A2->A3 promotion blocked (advisory gate): " + "; ".join(self.failures)
            )


def check_a2_to_a3_promotion(
    evidence: PromotionEvidence,
    *,
    agent_id: str,
    now: datetime | None = None,
) -> PromotionGateReport:
    """Evaluate the A2->A3 promotion gate against an attested record.

    Refuses promotion (collects a failure) when any lower-level control is
    unmet OR its attestation is invalid (self-attested, stale, evidence-
    less, or withheld). Returns the FULL failure list, not first-fail, so a
    deployer can remediate everything in one pass.
    """
    failures: list[str] = []

    # Sovereign veto must be load-tested, independently attested.
    ok, reason = evidence.sovereign_veto_load_tested.is_valid(agent_id=agent_id, now=now)
    if not ok:
        failures.append(f"sovereign_veto_load_tested invalid — {reason}")

    # Audit ledger must have been running >= 90 days, independently attested.
    if evidence.audit_ledger_running_for < timedelta(days=_MIN_AUDIT_LEDGER_DAYS):
        failures.append(
            f"audit_ledger_running_for {evidence.audit_ledger_running_for.days}d "
            f"< required {_MIN_AUDIT_LEDGER_DAYS}d"
        )
    ok, reason = evidence.audit_ledger_running_attestation.is_valid(agent_id=agent_id, now=now)
    if not ok:
        failures.append(f"audit_ledger attestation invalid — {reason}")

    # Shadow mode must have been running >= 30 days, independently attested.
    if evidence.shadow_mode_running_for < timedelta(days=_MIN_SHADOW_MODE_DAYS):
        failures.append(
            f"shadow_mode_running_for {evidence.shadow_mode_running_for.days}d "
            f"< required {_MIN_SHADOW_MODE_DAYS}d"
        )
    ok, reason = evidence.shadow_mode_attestation.is_valid(agent_id=agent_id, now=now)
    if not ok:
        failures.append(f"shadow_mode attestation invalid — {reason}")

    # Circuit breaker must have been tested recently, independently attested.
    ok, reason = evidence.circuit_breaker_test_recent.is_valid(agent_id=agent_id, now=now)
    if not ok:
        failures.append(f"circuit_breaker_test_recent invalid — {reason}")

    return PromotionGateReport(passed=not failures, failures=tuple(failures))


def required_oversight(level: AutonomyLevel) -> str:
    """Human-oversight requirement at each ladder level (advisory text)."""
    return {
        AutonomyLevel.A0: "Read-only; agent recommends, no write authority.",
        AutonomyLevel.A1: "Assisted; human approves every write.",
        AutonomyLevel.A2: "Delegated; agent writes in a hard envelope, sampled review.",
        AutonomyLevel.A3: "Supervised autonomous; sovereign veto + live ledger required.",
        AutonomyLevel.A4: "Production autonomous; A3 plus operator-validated escalation.",
    }[level]

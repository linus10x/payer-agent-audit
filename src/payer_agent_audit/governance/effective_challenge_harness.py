"""Effective Challenge Harness (P5) — independent model challenge as governance.

"Effective challenge" is the model-risk discipline (SR 11-7 in banking;
the same principle applies to a payer's UM/claims models) that a model's
outputs must be challenged by an *independent* party. This harness runs a
primary model and a challenger model over an evaluation set, measures
disagreement, and records the result — but only when the challenger is
genuinely independent of the primary.

P5 corrected-spec properties (the bar this is built to):
  * (a) ENFORCE in code: the challenger callable's identity must differ
    from the primary's. ``challenger is primary`` (or an attested-equal
    identity) is REJECTED — a model owner must not be able to
    self-challenge to a clean ``accept_primary``. A degenerate
    ``disagreement_rate == 0`` produced by an identical pair never yields
    an auto-accept.
  * (b) RECORD as attestation: independence is an OPERATOR-SUPPLIED claim
    (not same owner / not same vendor family / not same prompt template)
    plus WHO chose the challenger and WHEN, written to the audit chain.
    Vendor-family / prompt-template independence is ATTESTED, not
    code-detected — the harness cannot inspect a third-party vendor's
    model lineage, and it does not pretend to. It records the operator's
    attestation and fails closed if the attestation is missing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

if TYPE_CHECKING:
    from payer_agent_audit.governance.audit_chain import AuditChain

ModelCallable = Callable[[Any], Any]
Recommendation = Literal["accept_primary", "investigate", "escalate"]

_METHODOLOGY_ID = "effective_challenge_v1"
_DEFAULT_ACCEPT_THRESHOLD = 0.05
_DEFAULT_INVESTIGATE_THRESHOLD = 0.30


class ChallengerNotIndependentError(RuntimeError):
    """Raised when the challenger is not independent of the primary, or when
    the required independence attestation is missing/invalid."""


@dataclass(frozen=True)
class IndependenceAttestation:
    """Operator-supplied claim that the challenger is independent.

    These are ATTESTED facts, not code-detected — the harness records what
    the operator claims and binds WHO chose the challenger and WHEN. A
    false attestation is the operator's regulatory exposure; the harness
    makes the claim auditable, it does not adjudicate vendor lineage.
    """

    chosen_by: str  # operator/principal who selected the challenger
    chosen_at: str  # ISO-8601 UTC
    not_same_owner: bool
    not_same_vendor_family: bool
    not_same_prompt_template: bool
    rationale: str = ""

    def is_valid(self) -> tuple[bool, str]:
        if not self.chosen_by:
            return False, "chosen_by is empty (no principal recorded for the challenger choice)"
        if not (
            self.not_same_owner and self.not_same_vendor_family and self.not_same_prompt_template
        ):
            return False, (
                "independence attestation incomplete: all of not_same_owner, "
                "not_same_vendor_family, not_same_prompt_template must be attested True"
            )
        try:
            datetime.fromisoformat(self.chosen_at)
        except (ValueError, TypeError):
            return False, f"chosen_at {self.chosen_at!r} is not ISO-8601"
        return True, "ok"


@dataclass(frozen=True)
class ChallengeReport:
    """Outcome of an effective-challenge run."""

    primary_accuracy: float
    challenger_accuracy: float
    disagreement_rate: float
    n: int
    recommendation: Recommendation
    methodology: str = _METHODOLOGY_ID
    eval_set_hash: str = ""


class EffectiveChallengeHarness:
    """Runs an independent challenge of a primary model (P5)."""

    def __init__(
        self,
        *,
        primary_model: ModelCallable,
        challenger_model: ModelCallable,
        eval_set: list[tuple[Any, Any]],
        independence: IndependenceAttestation,
        audit_chain: AuditChain | None = None,
        accept_threshold: float = _DEFAULT_ACCEPT_THRESHOLD,
        investigate_threshold: float = _DEFAULT_INVESTIGATE_THRESHOLD,
        autonomy_level: AutonomyLevel = AutonomyLevel.A2,
        primary_id: str = "primary",
        challenger_id: str = "challenger",
    ) -> None:
        # P5(a) — ENFORCE challenger != primary in code.
        if challenger_model is primary_model:
            raise ChallengerNotIndependentError(
                "challenger_model is the SAME callable object as primary_model — "
                "a model cannot challenge itself. Self-challenge produces a "
                "degenerate disagreement_rate of 0 and a false accept_primary."
            )
        if primary_id == challenger_id:
            raise ChallengerNotIndependentError(
                f"primary_id and challenger_id are both {primary_id!r} — the "
                "challenger must be a distinct, identified model."
            )
        # P5(b) — independence attestation is mandatory and must be valid.
        ok, reason = independence.is_valid()
        if not ok:
            raise ChallengerNotIndependentError(f"independence attestation invalid: {reason}")

        self._primary = primary_model
        self._challenger = challenger_model
        self._eval_set = eval_set
        self._independence = independence
        self._audit_chain = audit_chain
        self._accept_threshold = accept_threshold
        self._investigate_threshold = investigate_threshold
        self._autonomy_level = autonomy_level
        self._primary_id = primary_id
        self._challenger_id = challenger_id

    def _recommend(self, disagreement_rate: float) -> Recommendation:
        if disagreement_rate <= self._accept_threshold:
            return "accept_primary"
        if disagreement_rate <= self._investigate_threshold:
            return "investigate"
        return "escalate"

    def _hash_eval_set(self) -> str:
        serial = json.dumps(
            [[repr(x), repr(y)] for x, y in self._eval_set], sort_keys=True
        ).encode()
        return hashlib.sha256(serial).hexdigest()

    def run(self, *, agent_id: str = "effective_challenge_harness") -> ChallengeReport:
        """Run the challenge and (optionally) record a MODEL_VALIDATED event."""
        n = len(self._eval_set)
        if n == 0:
            raise ValueError("eval_set is empty; cannot run an effective challenge")

        primary_correct = 0
        challenger_correct = 0
        disagreements = 0
        for x, expected in self._eval_set:
            p = self._primary(x)
            c = self._challenger(x)
            if p == expected:
                primary_correct += 1
            if c == expected:
                challenger_correct += 1
            if p != c:
                disagreements += 1

        disagreement_rate = disagreements / n
        report = ChallengeReport(
            primary_accuracy=primary_correct / n,
            challenger_accuracy=challenger_correct / n,
            disagreement_rate=disagreement_rate,
            n=n,
            recommendation=self._recommend(disagreement_rate),
            eval_set_hash=self._hash_eval_set(),
        )

        if self._audit_chain is not None:
            self._audit_chain.append(
                event_type=AuditEventType.MODEL_VALIDATED,
                autonomy_level=self._autonomy_level,
                agent_id=agent_id,
                payload={
                    "methodology": report.methodology,
                    "primary_id": self._primary_id,
                    "challenger_id": self._challenger_id,
                    "primary_accuracy": report.primary_accuracy,
                    "challenger_accuracy": report.challenger_accuracy,
                    "disagreement_rate": report.disagreement_rate,
                    "n": report.n,
                    "recommendation": report.recommendation,
                    "eval_set_hash": report.eval_set_hash,
                    # P5(b) — independence attestation written to the chain.
                    "independence_attestation": {
                        "chosen_by": self._independence.chosen_by,
                        "chosen_at": self._independence.chosen_at,
                        "not_same_owner": self._independence.not_same_owner,
                        "not_same_vendor_family": self._independence.not_same_vendor_family,
                        "not_same_prompt_template": self._independence.not_same_prompt_template,
                        "rationale": self._independence.rationale,
                        "attested": True,
                        "code_detected": False,
                    },
                    "recorded_at": datetime.now(UTC).isoformat(),
                },
                actor_id=self._independence.chosen_by,
            )

        return report

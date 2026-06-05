"""Appeal / IRO-pathway control (module a — health-payer).

On an adverse benefit determination, the member is entitled to an internal
appeal and — for non-grandfathered plans — an external review by an
Independent Review Organization (IRO). This control records that the appeal
rights were afforded and the external-review pathway routed, and enforces
the ERISA full-and-fair-review independence requirement (the appeal reviewer
must not be the original decision-maker and must not defer to the denial).

Boundary. This governs the PROCESS rights attached to a determination
(notice, internal appeal, IRO routing, reviewer independence). It does not
decide the appeal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from payer_agent_audit.payer.funding_type import FundingType, RequestCategory, obligations_for
from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

if TYPE_CHECKING:
    from payer_agent_audit.governance.audit_chain import AuditChain


class AppealRightsError(RuntimeError):
    """Raised when an adverse determination is recorded without affording the
    required appeal / external-review rights, or when the appeal reviewer is
    not independent of the original decision-maker."""


@dataclass(frozen=True)
class AppealPathway:
    """The appeal/external-review pathway afforded for a determination."""

    internal_appeal_offered: bool
    appeal_reviewer_id: str
    original_decision_maker_id: str
    external_review_offered: bool
    iro_assigned: bool
    iro_conflict_free: bool

    def independence_ok(self) -> tuple[bool, str]:
        """ERISA full-and-fair-review: reviewer != original decision-maker."""
        if not self.appeal_reviewer_id:
            return False, "appeal_reviewer_id is empty"
        if self.appeal_reviewer_id == self.original_decision_maker_id:
            return False, (
                "appeal reviewer is the original decision-maker — ERISA full-and-fair "
                "review (29 CFR 2560.503-1(h)) requires an independent reviewer who "
                "gives no deference to the initial denial"
            )
        return True, "ok"


class AppealIROControl:
    """Records and enforces appeal + IRO pathway on adverse determinations."""

    def __init__(self, audit_chain: AuditChain | None = None) -> None:
        self._chain = audit_chain

    def record_adverse_determination(
        self,
        *,
        case_ref: str,
        funding_type: FundingType,
        pathway: AppealPathway,
        category: RequestCategory = RequestCategory.STANDARD_PRESERVICE,
        agent_id: str = "appeal-iro-control",
    ) -> None:
        """Record an adverse benefit determination and gate its appeal rights.

        Enforces:
          * an internal appeal must be offered;
          * the appeal reviewer must be independent of the original
            decision-maker (ERISA full-and-fair review);
          * when external review is available for the funding type, the IRO
            pathway must be offered and the IRO conflict-free.
        Violations raise ``AppealRightsError`` and record a POLICY_VIOLATION.
        """
        obligation = obligations_for(funding_type, category)

        problems: list[str] = []
        if not pathway.internal_appeal_offered:
            problems.append("internal appeal not offered")
        ok, reason = pathway.independence_ok()
        if not ok:
            problems.append(reason)
        if obligation.external_review_available:
            if not pathway.external_review_offered:
                problems.append("external review available but not offered")
            elif pathway.iro_assigned and not pathway.iro_conflict_free:
                problems.append(
                    "IRO assigned but not attested conflict-free "
                    "(ACA 45 CFR 147.136 requires a no-conflict IRO)"
                )

        if problems:
            if self._chain is not None:
                self._chain.append(
                    event_type=AuditEventType.POLICY_VIOLATION,
                    autonomy_level=AutonomyLevel.A2,
                    agent_id=agent_id,
                    payload={
                        "control": "appeal_iro",
                        "case_ref": case_ref,
                        "funding_type": funding_type.value,
                        "violations": problems,
                    },
                )
            raise AppealRightsError(
                f"adverse determination for case {case_ref!r} failed appeal-rights "
                f"checks: {'; '.join(problems)}"
            )

        if self._chain is not None:
            self._chain.append(
                event_type=AuditEventType.ADVERSE_BENEFIT_DETERMINATION,
                autonomy_level=AutonomyLevel.A2,
                agent_id=agent_id,
                payload={
                    "case_ref": case_ref,
                    "funding_type": funding_type.value,
                    "appeal_regime": obligation.appeal_regime,
                    "internal_appeal_offered": pathway.internal_appeal_offered,
                    "appeal_reviewer_id": pathway.appeal_reviewer_id,
                    "external_review_offered": pathway.external_review_offered,
                    "iro_assigned": pathway.iro_assigned,
                    "iro_conflict_free": pathway.iro_conflict_free,
                    "external_review_citation": obligation.external_review_citation,
                },
            )
            if pathway.external_review_offered and pathway.iro_assigned:
                self._chain.append(
                    event_type=AuditEventType.EXTERNAL_REVIEW_ROUTED,
                    autonomy_level=AutonomyLevel.A2,
                    agent_id=agent_id,
                    payload={
                        "case_ref": case_ref,
                        "funding_type": funding_type.value,
                        "iro_conflict_free": pathway.iro_conflict_free,
                        "citation": obligation.external_review_citation,
                    },
                )

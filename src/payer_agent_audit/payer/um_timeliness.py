"""UM-timeliness control (module a — health-payer).

Checks whether a utilization-management / prior-authorization decision was
made within the deadline that the plan's funding type imposes, and records
the check to the audit chain. The deadline comes from the funding-type
obligation map (CMS-0057-F vs ERISA 29 CFR 2560.503-1 vs state DOI).

Boundary. This is a TIMELINESS governance check — did a decision land
inside the regulatory clock. It does NOT evaluate medical necessity or the
correctness of the decision itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from payer_agent_audit.payer.funding_type import (
    FundingType,
    ObligationSet,
    RequestCategory,
    obligations_for,
)
from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

if TYPE_CHECKING:
    from payer_agent_audit.governance.audit_chain import AuditChain


@dataclass(frozen=True)
class TimelinessResult:
    """Outcome of a UM-timeliness check."""

    funding_type: FundingType
    category: RequestCategory
    deadline: timedelta | None
    elapsed: timedelta
    met: bool | None  # None when the deadline is deployer-supplied/unknown
    citation: str
    citation_url: str
    verified_deadline: bool
    detail: str


class UMTimelinessControl:
    """Funding-type-aware UM-timeliness check with audit-chain recording."""

    def __init__(self, audit_chain: AuditChain | None = None) -> None:
        self._chain = audit_chain

    def check(
        self,
        *,
        funding_type: FundingType,
        category: RequestCategory,
        request_received_at: datetime,
        decision_made_at: datetime,
        agent_id: str = "um-timeliness-control",
        case_ref: str = "",
        deployer_deadline: timedelta | None = None,
    ) -> TimelinessResult:
        """Check a decision against its applicable deadline.

        ``deployer_deadline`` lets a deployer supply a state-specific or
        program-specific timeframe the library does not hardcode (e.g. a
        state UM statute). When the obligation map has a verified deadline,
        the deployer value is ignored unless it is STRICTER (shorter) — a
        deployer may tighten, never loosen, a regulatory floor.
        """
        if decision_made_at < request_received_at:
            raise ValueError("decision_made_at precedes request_received_at")

        obligation: ObligationSet = obligations_for(funding_type, category)
        deadline = obligation.timeliness.deadline
        verified = obligation.timeliness.verified

        # Deployer may supply a missing deadline, or TIGHTEN an existing one
        # (never loosen past a verified regulatory floor).
        if deployer_deadline is not None and (deadline is None or deployer_deadline < deadline):
            deadline = deployer_deadline

        elapsed = decision_made_at - request_received_at
        if deadline is None:
            met: bool | None = None
            detail = (
                f"No verified deadline for ({funding_type.value}, {category.value}); "
                f"supply a deployer_deadline from the primary source. "
                f"{obligation.timeliness.note}"
            )
        else:
            met = elapsed <= deadline
            detail = f"elapsed {elapsed} vs deadline {deadline} -> {'MET' if met else 'BREACHED'}"

        result = TimelinessResult(
            funding_type=funding_type,
            category=category,
            deadline=deadline,
            elapsed=elapsed,
            met=met,
            citation=obligation.timeliness.citation,
            citation_url=obligation.timeliness.citation_url,
            verified_deadline=verified,
            detail=detail,
        )

        if self._chain is not None:
            self._chain.append(
                event_type=AuditEventType.UM_TIMELINESS_CHECKED,
                autonomy_level=AutonomyLevel.A2,
                agent_id=agent_id,
                payload={
                    "case_ref": case_ref,
                    "funding_type": funding_type.value,
                    "category": category.value,
                    "request_received_at": request_received_at.isoformat(),
                    "decision_made_at": decision_made_at.isoformat(),
                    "deadline_seconds": None if deadline is None else deadline.total_seconds(),
                    "elapsed_seconds": elapsed.total_seconds(),
                    "met": met,
                    "citation": result.citation,
                    "citation_url": result.citation_url,
                    "verified_deadline": verified,
                },
            )

        return result

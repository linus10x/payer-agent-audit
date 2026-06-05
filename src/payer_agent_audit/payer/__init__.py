"""Health-payer control pack (module a — NAIC umbrella).

Funding-type-aware governance controls for autonomous AI agents in
utilization management, prior authorization, and claims/appeals workflows:

    funding_type        — CMS vs ERISA vs state-DOI obligation routing
    um_timeliness       — decision-deadline check (CMS-0057-F / ERISA / state)
    clinician_of_record — clinician-of-record-on-denial enforcement
    appeal_iro          — internal-appeal + IRO external-review pathway

These make NO medical-necessity / clinical determination. See LIMITATIONS.md
for the payer-not-FDA-SaMD boundary.
"""

from __future__ import annotations

from payer_agent_audit.payer.appeal_iro import (
    AppealIROControl,
    AppealPathway,
    AppealRightsError,
)
from payer_agent_audit.payer.clinician_of_record import (
    ClinicianOfRecord,
    ClinicianOfRecordControl,
    ClinicianOfRecordMissingError,
)
from payer_agent_audit.payer.funding_type import (
    FundingType,
    ObligationSet,
    RequestCategory,
    TimelinessObligation,
    obligations_for,
)
from payer_agent_audit.payer.um_timeliness import TimelinessResult, UMTimelinessControl

__all__ = [
    "AppealIROControl",
    "AppealPathway",
    "AppealRightsError",
    "ClinicianOfRecord",
    "ClinicianOfRecordControl",
    "ClinicianOfRecordMissingError",
    "FundingType",
    "ObligationSet",
    "RequestCategory",
    "TimelinessObligation",
    "TimelinessResult",
    "UMTimelinessControl",
    "obligations_for",
]

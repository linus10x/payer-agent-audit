"""Quickstart: wire UM-timeliness + clinician-of-record + appeal/IRO controls
to a hardened audit chain and verify the chain.

Run: python3 examples/quickstart_um_timeliness.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from payer_agent_audit.governance import AuditChain
from payer_agent_audit.payer import (
    AppealIROControl,
    AppealPathway,
    ClinicianOfRecord,
    ClinicianOfRecordControl,
    FundingType,
    RequestCategory,
    UMTimelinessControl,
)


def run() -> AuditChain:
    """Govern one Medicare Advantage prior-auth denial end to end."""
    chain = AuditChain(deployer_id="example-health-prod", in_memory=True)

    # 1. Timeliness — CMS-0057-F expedited (72h). Decided in 40h: MET.
    received = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    UMTimelinessControl(chain).check(
        funding_type=FundingType.MEDICARE_ADVANTAGE,
        category=RequestCategory.EXPEDITED_URGENT,
        request_received_at=received,
        decision_made_at=received + timedelta(hours=40),
        case_ref="PA-12345",
    )

    # 2. A medical-necessity denial requires an attested clinician of record.
    ClinicianOfRecordControl(chain).attest_denial(
        case_ref="PA-12345",
        is_medical_necessity_denial=True,
        clinician=ClinicianOfRecord(
            clinician_name="Dr. A. Reviewer",
            license_number="TX-12345",
            npi="1234567890",
            reviewed=True,
            same_or_similar_specialty=True,
        ),
    )

    # 3. Appeal + IRO pathway afforded, reviewer independent of decision-maker.
    AppealIROControl(chain).record_adverse_determination(
        case_ref="PA-12345",
        funding_type=FundingType.MEDICARE_ADVANTAGE,
        pathway=AppealPathway(
            internal_appeal_offered=True,
            appeal_reviewer_id="reviewer-2",
            original_decision_maker_id="reviewer-1",
            external_review_offered=True,
            iro_assigned=True,
            iro_conflict_free=True,
        ),
    )

    assert chain.verify()
    return chain


if __name__ == "__main__":
    c = run()
    print(f"chain verified: {c.verify()} ({len(c)} events), head={c.chain_head()[:16]}...")

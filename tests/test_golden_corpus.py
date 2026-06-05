"""Golden-corpus tests (spine §7 credibility tier).

Each real public matter of record is asserted to be GOVERNED by the
corresponding payer-agent-audit control. We assert control behavior, never a
litigation verdict or a clinical judgment. Every fixture carries a
primary-source URL (see ``golden_corpus.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from payer_agent_audit.governance import AuditChain
from payer_agent_audit.payer import (
    AppealIROControl,
    AppealPathway,
    AppealRightsError,
    ClinicianOfRecordControl,
    ClinicianOfRecordMissingError,
    FundingType,
    RequestCategory,
    UMTimelinessControl,
    obligations_for,
)

from .golden_corpus import ALL_GOLDEN, GOLDEN_LITIGATION, GOLDEN_REGULATION, GoldenCase


def _chain() -> AuditChain:
    return AuditChain(deployer_id="acme-health-prod", in_memory=True)


def test_every_golden_case_has_primary_source_and_is_verified():
    for case in ALL_GOLDEN:
        assert case.primary_source_url.startswith("https://"), case.case_id
        assert case.verified is True, case.case_id
        # matter_of_record must be a neutral statement (no verdict language).
        lowered = case.matter_of_record.lower()
        for banned in ("guilty", "liable", "we conclude", "proves that"):
            assert banned not in lowered, f"{case.case_id} carries characterization"


@pytest.mark.parametrize("case", GOLDEN_LITIGATION, ids=lambda c: c.case_id)
def test_litigation_clinician_of_record_governs(case: GoldenCase):
    """For each algorithmic-denial matter of record, the clinician-of-record
    control refuses a medical-necessity denial without an attested clinician."""
    assert case.governing_control == "clinician_of_record"
    chain = _chain()
    control = ClinicianOfRecordControl(audit_chain=chain)
    with pytest.raises(ClinicianOfRecordMissingError):
        control.attest_denial(
            case_ref=case.case_id,
            is_medical_necessity_denial=True,
            clinician=None,  # the scenario the matter of record describes
        )
    # The refusal is recorded as a policy violation (auditable).
    assert chain._events[-1].payload["violation"] == (
        "medical_necessity_denial_without_clinician_of_record"
    )


@pytest.mark.parametrize(
    "case",
    [c for c in GOLDEN_REGULATION if c.governing_control == "um_timeliness"],
    ids=lambda c: c.case_id,
)
def test_regulation_um_timeliness_matches_primary_source(case: GoldenCase):
    funding = FundingType(case.extra["funding_type"])
    category = RequestCategory(case.extra["category"])
    ob = obligations_for(funding, category)
    if "deadline_hours" in case.extra:
        assert ob.timeliness.deadline == timedelta(hours=int(case.extra["deadline_hours"]))
    if "deadline_days" in case.extra:
        assert ob.timeliness.deadline == timedelta(days=int(case.extra["deadline_days"]))
    assert ob.timeliness.verified is True

    # A breach is detected.
    chain = _chain()
    control = UMTimelinessControl(audit_chain=chain)
    received = datetime(2026, 6, 1, tzinfo=UTC)
    breach = ob.timeliness.deadline + timedelta(hours=1)
    result = control.check(
        funding_type=funding,
        category=category,
        request_received_at=received,
        decision_made_at=received + breach,
        case_ref=case.case_id,
    )
    assert result.met is False


@pytest.mark.parametrize(
    "case",
    [c for c in GOLDEN_REGULATION if c.governing_control == "appeal_iro"],
    ids=lambda c: c.case_id,
)
def test_regulation_appeal_iro_governs(case: GoldenCase):
    funding = FundingType(case.extra["funding_type"])
    control = AppealIROControl()
    # The matter of record: independence / conflict-free IRO required.
    bad = AppealPathway(
        internal_appeal_offered=True,
        appeal_reviewer_id="same",
        original_decision_maker_id="same",  # violates full-and-fair review
        external_review_offered=True,
        iro_assigned=True,
        iro_conflict_free=True,
    )
    with pytest.raises(AppealRightsError):
        control.record_adverse_determination(
            case_ref=case.case_id,
            funding_type=funding,
            pathway=bad,
        )


def test_naic_umbrella_case_present():
    umbrella = [c for c in GOLDEN_REGULATION if c.governing_control == "umbrella"]
    assert len(umbrella) == 1
    assert umbrella[0].extra["state_adoption_count"] == "24"

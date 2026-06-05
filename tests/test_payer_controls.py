"""Tests for the module-a health-payer control pack.

Funding-type routing (CMS vs ERISA vs state DOI), UM-timeliness,
clinician-of-record-on-denial, and appeal/IRO pathway controls. All wire to
the audit chain and the events are asserted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from payer_agent_audit.governance import AuditChain
from payer_agent_audit.payer import (
    AppealIROControl,
    AppealPathway,
    AppealRightsError,
    ClinicianOfRecord,
    ClinicianOfRecordControl,
    ClinicianOfRecordMissingError,
    FundingType,
    RequestCategory,
    UMTimelinessControl,
    obligations_for,
)
from payer_agent_audit.schemas.audit_event import AuditEventType


def _chain() -> AuditChain:
    return AuditChain(deployer_id="acme-health-prod", in_memory=True)


# --------------------------------------------------------------------------- #
# Funding-type obligation routing (CMS vs ERISA vs state DOI)                  #
# --------------------------------------------------------------------------- #


def test_routing_medicare_advantage_uses_cms():
    ob = obligations_for(FundingType.MEDICARE_ADVANTAGE, RequestCategory.EXPEDITED_URGENT)
    assert ob.primary_regulator == "CMS"
    assert ob.timeliness.deadline == timedelta(hours=72)
    assert ob.timeliness.verified is True
    assert "CMS-0057-F" in ob.timeliness.citation


def test_routing_self_funded_uses_erisa():
    ob = obligations_for(FundingType.SELF_FUNDED_ERISA, RequestCategory.STANDARD_PRESERVICE)
    assert ob.primary_regulator == "DOL (EBSA)"
    assert ob.timeliness.deadline == timedelta(days=15)  # 2560.503-1 pre-service
    assert "2560.503-1" in ob.timeliness.citation


def test_routing_self_funded_postservice_30_days():
    ob = obligations_for(FundingType.SELF_FUNDED_ERISA, RequestCategory.POSTSERVICE)
    assert ob.timeliness.deadline == timedelta(days=30)


def test_routing_fully_insured_state_doi_not_hardcoded():
    ob = obligations_for(FundingType.FULLY_INSURED, RequestCategory.STANDARD_PRESERVICE)
    assert ob.primary_regulator == "State Department of Insurance"
    # State-specific timeframe is NOT hardcoded — verified flag is False.
    assert ob.timeliness.deadline is None
    assert ob.timeliness.verified is False


def test_routing_qhp_ffe_excluded_from_cms_timeframe():
    ob = obligations_for(FundingType.QHP_FFE, RequestCategory.STANDARD_PRESERVICE)
    assert "147.136" in ob.timeliness.citation
    assert ob.external_review_available is True


def test_cms_expedited_is_distinct_from_erisa_urgent_value_but_same_72h():
    cms = obligations_for(FundingType.MEDICARE_ADVANTAGE, RequestCategory.EXPEDITED_URGENT)
    erisa = obligations_for(FundingType.SELF_FUNDED_ERISA, RequestCategory.EXPEDITED_URGENT)
    assert cms.timeliness.deadline == timedelta(hours=72)
    assert erisa.timeliness.deadline == timedelta(hours=72)
    # Different citations / regulators though.
    assert cms.timeliness.citation != erisa.timeliness.citation


# --------------------------------------------------------------------------- #
# UM-timeliness control                                                        #
# --------------------------------------------------------------------------- #


def test_um_timeliness_met_for_cms_expedited():
    chain = _chain()
    control = UMTimelinessControl(audit_chain=chain)
    received = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    decided = received + timedelta(hours=40)  # within 72h
    result = control.check(
        funding_type=FundingType.MEDICARE_ADVANTAGE,
        category=RequestCategory.EXPEDITED_URGENT,
        request_received_at=received,
        decision_made_at=decided,
        case_ref="C-1",
    )
    assert result.met is True
    # Event recorded.
    assert chain._events[-1].event_type == AuditEventType.UM_TIMELINESS_CHECKED
    assert chain._events[-1].payload["met"] is True


def test_um_timeliness_breached_for_erisa_preservice():
    chain = _chain()
    control = UMTimelinessControl(audit_chain=chain)
    received = datetime(2026, 6, 1, tzinfo=UTC)
    decided = received + timedelta(days=20)  # > 15 days
    result = control.check(
        funding_type=FundingType.SELF_FUNDED_ERISA,
        category=RequestCategory.STANDARD_PRESERVICE,
        request_received_at=received,
        decision_made_at=decided,
        case_ref="C-2",
    )
    assert result.met is False


def test_um_timeliness_state_doi_requires_deployer_deadline():
    control = UMTimelinessControl()
    received = datetime(2026, 6, 1, tzinfo=UTC)
    decided = received + timedelta(days=2)
    # No hardcoded deadline -> met is None until deployer supplies one.
    result = control.check(
        funding_type=FundingType.FULLY_INSURED,
        category=RequestCategory.STANDARD_PRESERVICE,
        request_received_at=received,
        decision_made_at=decided,
    )
    assert result.met is None
    # Supply a state-specific deadline.
    result2 = control.check(
        funding_type=FundingType.FULLY_INSURED,
        category=RequestCategory.STANDARD_PRESERVICE,
        request_received_at=received,
        decision_made_at=decided,
        deployer_deadline=timedelta(days=5),
    )
    assert result2.met is True


def test_um_timeliness_deployer_may_tighten_not_loosen():
    control = UMTimelinessControl()
    received = datetime(2026, 6, 1, tzinfo=UTC)
    decided = received + timedelta(hours=60)
    # Deployer supplies a STRICTER 48h deadline for CMS expedited (72h floor).
    result = control.check(
        funding_type=FundingType.MEDICARE_ADVANTAGE,
        category=RequestCategory.EXPEDITED_URGENT,
        request_received_at=received,
        decision_made_at=decided,
        deployer_deadline=timedelta(hours=48),
    )
    # 60h > tightened 48h -> breached.
    assert result.deadline == timedelta(hours=48)
    assert result.met is False
    # Deployer cannot LOOSEN past the 72h regulatory floor.
    result2 = control.check(
        funding_type=FundingType.MEDICARE_ADVANTAGE,
        category=RequestCategory.EXPEDITED_URGENT,
        request_received_at=received,
        decision_made_at=decided,
        deployer_deadline=timedelta(hours=200),  # attempt to loosen
    )
    assert result2.deadline == timedelta(hours=72)  # floor held


def test_um_timeliness_rejects_decision_before_request():
    control = UMTimelinessControl()
    received = datetime(2026, 6, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="precedes"):
        control.check(
            funding_type=FundingType.MEDICARE_ADVANTAGE,
            category=RequestCategory.EXPEDITED_URGENT,
            request_received_at=received,
            decision_made_at=received - timedelta(hours=1),
        )


# --------------------------------------------------------------------------- #
# Clinician-of-record-on-denial                                               #
# --------------------------------------------------------------------------- #


def test_clinician_of_record_required_for_medical_necessity_denial():
    chain = _chain()
    control = ClinicianOfRecordControl(audit_chain=chain)
    with pytest.raises(ClinicianOfRecordMissingError, match="clinician of record"):
        control.attest_denial(
            case_ref="D-1",
            is_medical_necessity_denial=True,
            clinician=None,  # algorithmic denial without a clinician -> refused
        )
    # The refused denial is itself recorded as a policy violation.
    assert chain._events[-1].event_type == AuditEventType.POLICY_VIOLATION
    assert chain._events[-1].payload["violation"] == (
        "medical_necessity_denial_without_clinician_of_record"
    )


def test_clinician_must_attest_review_not_just_name():
    chain = _chain()
    control = ClinicianOfRecordControl(audit_chain=chain)
    unreviewed = ClinicianOfRecord(
        clinician_name="Dr. A. Reviewer",
        license_number="TX-12345",
        npi="1234567890",
        reviewed=False,  # name attached but did not actually review
    )
    with pytest.raises(ClinicianOfRecordMissingError, match="did not attest review"):
        control.attest_denial(
            case_ref="D-2",
            is_medical_necessity_denial=True,
            clinician=unreviewed,
        )


def test_clinician_of_record_valid_denial_records_attestation():
    chain = _chain()
    control = ClinicianOfRecordControl(audit_chain=chain)
    clinician = ClinicianOfRecord(
        clinician_name="Dr. A. Reviewer",
        license_number="TX-12345",
        npi="1234567890",
        reviewed=True,
        same_or_similar_specialty=True,
    )
    control.attest_denial(
        case_ref="D-3",
        is_medical_necessity_denial=True,
        clinician=clinician,
    )
    assert chain._events[-1].event_type == AuditEventType.CLINICIAN_OF_RECORD_ATTESTED
    assert chain._events[-1].payload["reviewed"] is True


def test_non_medical_necessity_denial_does_not_require_clinician():
    chain = _chain()
    control = ClinicianOfRecordControl(audit_chain=chain)
    # An eligibility/benefit-terms denial does not need a clinician.
    control.attest_denial(
        case_ref="D-4",
        is_medical_necessity_denial=False,
        clinician=None,
    )
    assert chain._events[-1].event_type == AuditEventType.CLINICIAN_OF_RECORD_ATTESTED


# --------------------------------------------------------------------------- #
# Appeal / IRO pathway                                                        #
# --------------------------------------------------------------------------- #


def _good_pathway() -> AppealPathway:
    return AppealPathway(
        internal_appeal_offered=True,
        appeal_reviewer_id="reviewer-2",
        original_decision_maker_id="reviewer-1",
        external_review_offered=True,
        iro_assigned=True,
        iro_conflict_free=True,
    )


def test_appeal_pathway_records_adverse_determination_and_iro_route():
    chain = _chain()
    control = AppealIROControl(audit_chain=chain)
    control.record_adverse_determination(
        case_ref="A-1",
        funding_type=FundingType.SELF_FUNDED_ERISA,
        pathway=_good_pathway(),
    )
    types = [e.event_type for e in chain._events]
    assert AuditEventType.ADVERSE_BENEFIT_DETERMINATION in types
    assert AuditEventType.EXTERNAL_REVIEW_ROUTED in types


def test_appeal_reviewer_cannot_be_original_decision_maker():
    chain = _chain()
    control = AppealIROControl(audit_chain=chain)
    pathway = AppealPathway(
        internal_appeal_offered=True,
        appeal_reviewer_id="reviewer-1",
        original_decision_maker_id="reviewer-1",  # not independent
        external_review_offered=True,
        iro_assigned=True,
        iro_conflict_free=True,
    )
    with pytest.raises(AppealRightsError, match="independent reviewer"):
        control.record_adverse_determination(
            case_ref="A-2",
            funding_type=FundingType.SELF_FUNDED_ERISA,
            pathway=pathway,
        )
    assert chain._events[-1].event_type == AuditEventType.POLICY_VIOLATION


def test_appeal_requires_internal_appeal_offered():
    control = AppealIROControl()
    pathway = AppealPathway(
        internal_appeal_offered=False,
        appeal_reviewer_id="reviewer-2",
        original_decision_maker_id="reviewer-1",
        external_review_offered=True,
        iro_assigned=True,
        iro_conflict_free=True,
    )
    with pytest.raises(AppealRightsError, match="internal appeal not offered"):
        control.record_adverse_determination(
            case_ref="A-3",
            funding_type=FundingType.FULLY_INSURED,
            pathway=pathway,
        )


def test_iro_must_be_conflict_free():
    control = AppealIROControl()
    pathway = AppealPathway(
        internal_appeal_offered=True,
        appeal_reviewer_id="reviewer-2",
        original_decision_maker_id="reviewer-1",
        external_review_offered=True,
        iro_assigned=True,
        iro_conflict_free=False,  # conflicted IRO
    )
    with pytest.raises(AppealRightsError, match="conflict-free"):
        control.record_adverse_determination(
            case_ref="A-4",
            funding_type=FundingType.QHP_FFE,
            pathway=pathway,
        )


# --------------------------------------------------------------------------- #
# Supplemental coverage — schema re-export + clinician validity branches       #
# --------------------------------------------------------------------------- #


def test_schemas_package_reexports_auditchain():
    import payer_agent_audit.schemas as s

    assert s.AuditChain is AuditChain
    with pytest.raises(AttributeError):
        _ = s.DoesNotExist  # type: ignore[attr-defined]


def test_audit_event_module_reexports_auditchain():
    import payer_agent_audit.schemas.audit_event as ae

    assert ae.AuditChain is AuditChain
    with pytest.raises(AttributeError):
        _ = ae.Nope  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "name,lic,npi,reason",
    [
        ("", "L1", "N1", "clinician_name"),
        ("Dr X", "", "N1", "license_number"),
        ("Dr X", "L1", "", "npi"),
    ],
)
def test_clinician_of_record_field_validation(name, lic, npi, reason):
    from payer_agent_audit.payer import ClinicianOfRecord

    c = ClinicianOfRecord(clinician_name=name, license_number=lic, npi=npi, reviewed=True)
    ok, msg = c.is_valid()
    assert not ok and reason in msg


# --------------------------------------------------------------------------- #
# Post-adversarial-review hardening                                            #
# --------------------------------------------------------------------------- #


def test_medicaid_managed_care_uses_438_210_not_generic_cms():
    """Medicaid MC routes to 42 CFR 438.210(d), a distinct authority from MA."""
    ob = obligations_for(FundingType.MEDICAID_MANAGED_CARE, RequestCategory.STANDARD_PRESERVICE)
    assert "438.210" in ob.timeliness.citation
    assert ob.timeliness.deadline == timedelta(days=7)  # 7d on/after 2026-01-01
    assert ob.primary_regulator == "CMS + State Medicaid agency"
    # MA still uses CMS-0057-F, a different citation.
    ma = obligations_for(FundingType.MEDICARE_ADVANTAGE, RequestCategory.STANDARD_PRESERVICE)
    assert "CMS-0057-F" in ma.timeliness.citation
    assert ma.timeliness.citation != ob.timeliness.citation


def test_chip_routes_to_medicaid_table():
    ob = obligations_for(FundingType.CHIP, RequestCategory.EXPEDITED_URGENT)
    assert "438.210" in ob.timeliness.citation
    assert ob.timeliness.deadline == timedelta(hours=72)


def test_qhp_ffe_deadline_none_is_not_marked_verified():
    """No verified DECISION deadline for QHP-FFE — verified must be False to
    avoid a verified-True/deadline-None contradiction."""
    ob = obligations_for(FundingType.QHP_FFE, RequestCategory.STANDARD_PRESERVICE)
    assert ob.timeliness.deadline is None
    assert ob.timeliness.verified is False


def test_clinician_specialty_match_can_be_enforced():
    chain = _chain()
    control = ClinicianOfRecordControl(audit_chain=chain)
    no_specialty = ClinicianOfRecord(
        clinician_name="Dr. A",
        license_number="TX-1",
        npi="1234567890",
        reviewed=True,
        same_or_similar_specialty=False,
    )
    # Default: not gated -> recorded.
    control.attest_denial(case_ref="S-1", is_medical_necessity_denial=True, clinician=no_specialty)
    assert chain._events[-1].event_type == AuditEventType.CLINICIAN_OF_RECORD_ATTESTED
    # With require_specialty_match=True -> refused.
    with pytest.raises(ClinicianOfRecordMissingError, match="specialty"):
        control.attest_denial(
            case_ref="S-2",
            is_medical_necessity_denial=True,
            clinician=no_specialty,
            require_specialty_match=True,
        )

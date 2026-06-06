"""Round-3 hardening tests.

Unicode-confusable / zero-width guard bypass class, surviving-mutant boundary
tests, prev_hash-mismatch tamper detection, DEFCON+promotion chain wiring, and
the remaining reachable defensive branches.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from payer_agent_audit._normalize import normalize_principal_id
from payer_agent_audit.governance import (
    DEFCON,
    Attestation,
    AuditChain,
    AuditChainTamperError,
    DEFCONMachine,
    EffectiveChallengeHarness,
    IndependenceAttestation,
    InMemoryWitness,
    PromotionEvidence,
    RiskMetrics,
    SovereignVeto,
    VetoBlockedError,
    VetoReason,
    anchor_to_witness,
    check_a2_to_a3_promotion,
    required_oversight,
)
from payer_agent_audit.payer import (
    AppealIROControl,
    AppealPathway,
    AppealRightsError,
    ClinicianOfRecord,
    FundingType,
    RequestCategory,
    UMTimelinessControl,
)
from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel


def _allow():
    class _A:
        def authorize(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
            return True

    return _A()


# --------------------------------------------------------------------------- #
# Unicode-confusable / zero-width identity guard bypass class                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "disguise",
    [
        "ａgent-x",  # fullwidth a (NFKC-folds to 'agent-x')
        "agent-x​",  # trailing zero-width space
        "age‍nt-x",  # zero-width joiner inside
        "AGENT-X",
        " agent-x ",
        "﻿agent-x",  # BOM prefix
    ],
)
def test_normalize_collapses_confusables_and_zero_width(disguise):
    assert normalize_principal_id(disguise) == normalize_principal_id("agent-x")


def test_p1_self_attestation_confusable_bypass_blocked():
    a = Attestation("c", "ａgent-x", datetime.now(UTC).isoformat(), "ref")
    ok, reason = a.is_valid(agent_id="agent-x")
    assert not ok and "self-attestation rejected" in reason


def test_p2_self_clear_confusable_bypass_blocked():
    v = SovereignVeto("agent-x", authorizer=_allow(), production=True)
    v.trigger(VetoReason.COMPLIANCE_FLAG, "officer", "flag")
    with pytest.raises(VetoBlockedError, match="self-clearing forbidden"):
        v.clear(operator_id="agent-x​", reason="resume")
    assert v.is_vetoed


def test_appeal_independence_confusable_bypass_blocked():
    control = AppealIROControl()
    pathway = AppealPathway(
        internal_appeal_offered=True,
        appeal_reviewer_id="dr-smith​",
        original_decision_maker_id="DR-SMITH",  # same human, disguised
        external_review_offered=True,
        iro_assigned=True,
        iro_conflict_free=True,
    )
    with pytest.raises(AppealRightsError, match="independent reviewer"):
        control.record_adverse_determination(
            case_ref="A-c", funding_type=FundingType.SELF_FUNDED_ERISA, pathway=pathway
        )


def test_clinician_whitespace_only_fields_rejected():
    c = ClinicianOfRecord(clinician_name="   ", license_number=" ", npi="\t", reviewed=True)
    ok, reason = c.is_valid()
    assert not ok and "blank" in reason


# --------------------------------------------------------------------------- #
# Surviving-mutant boundary tests (M11/M12/M13)                                #
# --------------------------------------------------------------------------- #


def test_um_deployer_deadline_equal_does_not_replace():
    """M11: deployer_deadline == verified deadline must NOT replace it (strict
    `<` tighten-only semantics; equality is a no-op, not a swap)."""
    control = UMTimelinessControl()
    received = datetime(2026, 6, 1, tzinfo=UTC)
    # CMS expedited floor is 72h; supply exactly 72h — must stay the verified one.
    result = control.check(
        funding_type=FundingType.MEDICARE_ADVANTAGE,
        category=RequestCategory.EXPEDITED_URGENT,
        request_received_at=received,
        decision_made_at=received + timedelta(hours=71),
        deployer_deadline=timedelta(hours=72),
    )
    assert result.deadline == timedelta(hours=72)
    assert result.verified_deadline is True  # the verified obligation, not the deployer value


def test_um_zero_elapsed_allowed():
    """M13: decision_made_at == request_received_at is allowed (0 elapsed, met)."""
    control = UMTimelinessControl()
    t = datetime(2026, 6, 1, tzinfo=UTC)
    result = control.check(
        funding_type=FundingType.MEDICARE_ADVANTAGE,
        category=RequestCategory.EXPEDITED_URGENT,
        request_received_at=t,
        decision_made_at=t,
    )
    assert result.met is True
    assert result.elapsed == timedelta(0)


def test_appeal_external_offered_but_iro_not_assigned_passes():
    """M12: external_review_offered=True, iro_assigned=False is permitted
    (assignment happens when the member requests external review)."""
    chain = AuditChain(deployer_id="acme", in_memory=True)
    control = AppealIROControl(audit_chain=chain)
    pathway = AppealPathway(
        internal_appeal_offered=True,
        appeal_reviewer_id="reviewer-2",
        original_decision_maker_id="reviewer-1",
        external_review_offered=True,
        iro_assigned=False,
        iro_conflict_free=False,  # irrelevant while unassigned
    )
    control.record_adverse_determination(
        case_ref="A-m12", funding_type=FundingType.SELF_FUNDED_ERISA, pathway=pathway
    )
    types = [e.event_type for e in chain._events]
    assert AuditEventType.ADVERSE_BENEFIT_DETERMINATION in types
    assert AuditEventType.EXTERNAL_REVIEW_ROUTED not in types  # not routed until assigned


# --------------------------------------------------------------------------- #
# P3 prev_hash-mismatch detection                                              #
# --------------------------------------------------------------------------- #


def test_chain_prev_hash_link_break_detected():
    chain = AuditChain(deployer_id="acme", in_memory=True)
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um",
        payload={"d": 1},
    )
    e2 = chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um",
        payload={"d": 2},
    )
    # Break the chain LINK (prev_hash) without touching event_hash recompute:
    # set prev_hash to a wrong-but-well-formed value and recompute its own hash
    # so the event_hash check passes but the prev_hash link is broken.
    object.__setattr__(e2, "prev_hash", "f" * 64)
    object.__setattr__(e2, "event_hash", e2._compute_hash())
    assert chain.verify() is False
    with pytest.raises(AuditChainTamperError, match="prev_hash mismatch"):
        chain.verify_strict()


# --------------------------------------------------------------------------- #
# DEFCON + promotion-gate chain wiring                                         #
# --------------------------------------------------------------------------- #


def test_defcon_emits_to_audit_chain():
    chain = AuditChain(deployer_id="acme", in_memory=True)
    m = DEFCONMachine(authorizer=_allow(), production=True, audit_chain=chain)
    m.evaluate(RiskMetrics(breach_rate=0.12))  # -> ALERT (escalation)
    m.manual_override(DEFCON.HALT, "ops", "stop")  # -> HALT
    types = [e.event_type for e in chain._events]
    assert AuditEventType.RISK_ESCALATION in types
    assert AuditEventType.HALT_TRIGGERED in types
    # De-escalation one level (HALT->DANGER) emits RISK_DEESCALATION.
    m.manual_override(DEFCON.DANGER, "ops", "step down")
    assert AuditEventType.RISK_DEESCALATION in [e.event_type for e in chain._events]
    assert chain.verify()


def test_promotion_gate_emits_to_audit_chain():
    chain = AuditChain(deployer_id="acme", in_memory=True)

    def att(claim):  # noqa: ANN001, ANN202
        return Attestation(claim, "mrm", datetime.now(UTC).isoformat(), "ref")

    ev = PromotionEvidence(
        sovereign_veto_load_tested=att("v"),
        audit_ledger_running_for=timedelta(days=120),
        audit_ledger_running_attestation=att("l"),
        shadow_mode_running_for=timedelta(days=45),
        shadow_mode_attestation=att("s"),
        circuit_breaker_test_recent=att("cb"),
    )
    report = check_a2_to_a3_promotion(ev, agent_id="agent", audit_chain=chain)
    assert report.passed is True
    assert chain._events[-1].event_type == AuditEventType.PROMOTION_GATE_EVALUATED
    assert chain._events[-1].payload["passed"] is True


# --------------------------------------------------------------------------- #
# Remaining reachable defensive branches                                       #
# --------------------------------------------------------------------------- #


def test_chain_production_requires_deployer_id():
    with pytest.raises(ValueError, match="requires an explicit deployer_id"):
        AuditChain(production=True, witness_register=InMemoryWitness(), in_memory=True)


def test_independence_empty_chosen_by_rejected():
    from payer_agent_audit.governance import ChallengerNotIndependentError

    bad = IndependenceAttestation(
        chosen_by="",
        chosen_at=datetime.now(UTC).isoformat(),
        not_same_owner=True,
        not_same_vendor_family=True,
        not_same_prompt_template=True,
    )
    with pytest.raises(ChallengerNotIndependentError, match="chosen_by"):
        EffectiveChallengeHarness(
            primary_model=lambda x: x,
            challenger_model=lambda x: x + 1,
            eval_set=[(1, 1)],
            independence=bad,
        )


def test_appeal_empty_reviewer_rejected():
    control = AppealIROControl()
    pathway = AppealPathway(
        internal_appeal_offered=True,
        appeal_reviewer_id="  ",
        original_decision_maker_id="reviewer-1",
        external_review_offered=True,
        iro_assigned=True,
        iro_conflict_free=True,
    )
    with pytest.raises(AppealRightsError, match="empty/blank"):
        control.record_adverse_determination(
            case_ref="A-e", funding_type=FundingType.SELF_FUNDED_ERISA, pathway=pathway
        )


def test_appeal_external_available_but_not_offered_rejected():
    control = AppealIROControl()
    pathway = AppealPathway(
        internal_appeal_offered=True,
        appeal_reviewer_id="reviewer-2",
        original_decision_maker_id="reviewer-1",
        external_review_offered=False,  # available but not offered
        iro_assigned=False,
        iro_conflict_free=False,
    )
    with pytest.raises(AppealRightsError, match="external review available but not offered"):
        control.record_adverse_determination(
            case_ref="A-no", funding_type=FundingType.SELF_FUNDED_ERISA, pathway=pathway
        )


def test_veto_clear_specific_veto_id_skips_others():
    v = SovereignVeto("agent", authorizer=_allow(), production=True)
    r1 = v.trigger(VetoReason.RISK_LIMIT_BREACH, "op", "first")
    v.trigger(VetoReason.ANOMALY_DETECTED, "op", "second")
    cleared = v.clear(operator_id="op-2", reason="ok", veto_id=r1.veto_id)
    assert len(cleared) == 1 and cleared[0].veto_id == r1.veto_id
    assert v.is_vetoed  # the second veto remains active


def test_anchor_to_witness_function_form():
    witness = InMemoryWitness()
    chain = AuditChain(deployer_id="acme", in_memory=True)
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um",
        payload={"d": 1},
    )
    ev = anchor_to_witness(audit_chain=chain, witness=witness)
    assert ev.event_type == AuditEventType.WITNESS_ANCHOR
    assert len(witness.anchored) == 1


def test_required_oversight_returns_text():
    assert "veto" in required_oversight(AutonomyLevel.A3).lower()


def test_chain_load_skips_blank_lines(tmp_path):
    log = tmp_path / "c.jsonl"
    chain = AuditChain(log_file=log, deployer_id="acme")
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um",
        payload={"d": 1},
    )
    # Inject a blank line; reload must skip it and still verify.
    text = log.read_text()
    log.write_text(text + "\n   \n")
    reloaded = AuditChain(log_file=log, deployer_id="acme")
    assert reloaded.verify() is True


def test_veto_reclear_skips_already_cleared():
    v = SovereignVeto("agent", authorizer=_allow(), production=True)
    v.trigger(VetoReason.RISK_LIMIT_BREACH, "op", "d")
    v.clear(operator_id="op-2", reason="ok")
    assert not v.is_vetoed
    # Second clear iterates over an already-cleared record (the skip branch).
    cleared = v.clear(operator_id="op-2", reason="again")
    assert cleared == []

"""AL-PROBES — the five primitive adversarial probes (Tier-1 audit protocol).

Each probe re-authors the catalog's exact failing construction as a
committed, reproducible test, and asserts that payer-agent-audit's
corrected-spec primitive REFUSES the attack. These are the reproducible
evidence that the five primitives meet the §2 corrected standard — they
do NOT replicate finserv's historical defects (AL-PROBE-02/03b/05).

  AL-PROBE-01  P1  promote-without-lower-gates -> refused
  AL-PROBE-02  P2  self-clear / unauthenticated-operator veto clear -> refused
  AL-PROBE-03  P3  in-place tamper AND end-to-end genesis branch -> detected/verifies
  AL-PROBE-04  P4  illegal one-call HALT/SHUTDOWN -> NORMAL -> refused
  AL-PROBE-05  P5  self-challenge (challenger == primary) -> rejected
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from payer_agent_audit.governance import (
    DEFCON,
    Attestation,
    AuditChain,
    AuditChainTamperError,
    ChallengerNotIndependentError,
    DEFCONMachine,
    DEFCONOverrideRejectedError,
    EffectiveChallengeHarness,
    IndependenceAttestation,
    InMemoryWitness,
    PromotionEvidence,
    SovereignVeto,
    VetoBlockedError,
    VetoReason,
    check_a2_to_a3_promotion,
)
from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

# --------------------------------------------------------------------------- #
# Shared test doubles                                                         #
# --------------------------------------------------------------------------- #


class AllowAuthorizer:
    """A permissive Authorizer — used to prove self-clear is rejected EVEN
    when the authorizer would allow it (the unconditional guard)."""

    def authorize(self, operator_id, action, context):  # noqa: ANN001, ANN201
        return True


class PrincipalAuthorizer:
    """Authorizes only a fixed allow-list of authenticated principals."""

    def __init__(self, allowed):  # noqa: ANN001
        self._allowed = set(allowed)

    def authorize(self, operator_id, action, context):  # noqa: ANN001, ANN201
        return operator_id in self._allowed


def _fresh_attestation(claim: str, attester: str = "second-line-mrm") -> Attestation:
    return Attestation(
        claim=claim,
        attester_id=attester,
        attested_at=datetime.now(UTC).isoformat(),
        evidence_ref=f"s3://evidence/{claim}.pdf",
        value=True,
    )


# --------------------------------------------------------------------------- #
# AL-PROBE-01 — P1 promote-without-lower-gates -> refused                      #
# --------------------------------------------------------------------------- #


def test_al_probe_01_promote_without_lower_gates_refused():
    """An agent presenting unmet lower-level controls must NOT be promoted."""
    agent = "um-autonomy-agent"
    # Lower controls unmet: ledger only 10 days, shadow only 5 days.
    evidence = PromotionEvidence(
        sovereign_veto_load_tested=_fresh_attestation("veto_load_tested"),
        audit_ledger_running_for=timedelta(days=10),
        audit_ledger_running_attestation=_fresh_attestation("ledger_uptime"),
        shadow_mode_running_for=timedelta(days=5),
        shadow_mode_attestation=_fresh_attestation("shadow_uptime"),
        circuit_breaker_test_recent=_fresh_attestation("circuit_breaker"),
    )
    report = check_a2_to_a3_promotion(evidence, agent_id=agent)
    assert report.passed is False
    assert any("audit_ledger_running_for" in f for f in report.failures)
    assert any("shadow_mode_running_for" in f for f in report.failures)


def test_al_probe_01b_self_attestation_rejected():
    """The gate must reject caller-asserted self-attestation — it requires an
    INDEPENDENT attester, not a bool the agent vouches for itself."""
    agent = "um-autonomy-agent"
    self_attested = Attestation(
        claim="veto_load_tested",
        attester_id=agent,  # self-attestation
        attested_at=datetime.now(UTC).isoformat(),
        evidence_ref="self://claim",
        value=True,
    )
    evidence = PromotionEvidence(
        sovereign_veto_load_tested=self_attested,
        audit_ledger_running_for=timedelta(days=120),
        audit_ledger_running_attestation=_fresh_attestation("ledger_uptime"),
        shadow_mode_running_for=timedelta(days=45),
        shadow_mode_attestation=_fresh_attestation("shadow_uptime"),
        circuit_breaker_test_recent=_fresh_attestation("circuit_breaker"),
    )
    report = check_a2_to_a3_promotion(evidence, agent_id=agent)
    assert report.passed is False
    assert any("self-attestation rejected" in f for f in report.failures)


def test_al_probe_01c_fully_attested_promotion_passes():
    """Positive control — a complete, fresh, independently-attested record
    with satisfied lower controls passes."""
    agent = "um-autonomy-agent"
    evidence = PromotionEvidence(
        sovereign_veto_load_tested=_fresh_attestation("veto_load_tested"),
        audit_ledger_running_for=timedelta(days=120),
        audit_ledger_running_attestation=_fresh_attestation("ledger_uptime"),
        shadow_mode_running_for=timedelta(days=45),
        shadow_mode_attestation=_fresh_attestation("shadow_uptime"),
        circuit_breaker_test_recent=_fresh_attestation("circuit_breaker"),
    )
    report = check_a2_to_a3_promotion(evidence, agent_id=agent)
    assert report.passed is True
    assert report.failures == ()


# --------------------------------------------------------------------------- #
# AL-PROBE-02 — P2 self-clear / unauthenticated clear -> refused               #
# --------------------------------------------------------------------------- #


def test_al_probe_02_agent_cannot_self_clear_even_with_permissive_authorizer():
    veto = SovereignVeto("claims-agent", authorizer=AllowAuthorizer(), production=True)
    veto.trigger(VetoReason.COMPLIANCE_FLAG, "compliance-officer", "denial pattern flagged")
    assert veto.is_vetoed
    # The agent tries to clear its own veto — must be refused unconditionally,
    # even though the authorizer would say yes.
    with pytest.raises(VetoBlockedError, match="self-clearing forbidden"):
        veto.clear(operator_id="claims-agent", reason="resume")
    assert veto.is_vetoed  # still blocked


def test_al_probe_02b_unauthenticated_operator_refused_in_production():
    veto = SovereignVeto(
        "claims-agent",
        authorizer=PrincipalAuthorizer(allowed={"med-director-42"}),
        production=True,
    )
    veto.trigger(VetoReason.MANUAL_OPERATOR, "med-director-42", "manual hold")
    # An operator the IdP does not vouch for is rejected.
    with pytest.raises(VetoBlockedError, match="not an authenticated principal"):
        veto.clear(operator_id="random-string", reason="resume")
    assert veto.is_vetoed
    # The authenticated principal CAN clear it.
    cleared = veto.clear(operator_id="med-director-42", reason="reviewed, safe to resume")
    assert len(cleared) == 1
    assert veto.allow_execution()


def test_al_probe_02c_production_requires_authorizer():
    with pytest.raises(ValueError, match="requires an authorizer"):
        SovereignVeto("claims-agent", production=True)


# --------------------------------------------------------------------------- #
# AL-PROBE-03 — P3 in-place tamper detected AND hardened/legacy both verify    #
# --------------------------------------------------------------------------- #


def test_al_probe_03_hardened_chain_verifies_true():
    """The catalog defect (AL-PROBE-03b): a clean deployer-keyed chain raised
    a false TAMPER because the verifier seeded '0'*64 unconditionally. Our
    verifier BRANCHES the genesis seed, so a hardened chain verifies True."""
    chain = AuditChain(deployer_id="acme-health-prod", in_memory=True)
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um-agent",
        payload={"decision": "approved", "service": "post-acute"},
    )
    assert chain.verify() is True
    chain.verify_strict()  # does not raise


def test_al_probe_03b_legacy_chain_also_verifies_true():
    """Both a hardened chain AND a legacy ('0'*64) chain must verify True —
    the sentinel branch is retained, not globally removed."""
    chain = AuditChain(in_memory=True)  # legacy: no deployer_id
    chain.append(
        event_type=AuditEventType.COVERAGE_DETERMINATION,
        autonomy_level=AutonomyLevel.A1,
        agent_id="coverage-agent",
        payload={"determination": "covered"},
    )
    assert chain.verify() is True


def test_al_probe_03c_in_place_tamper_detected():
    chain = AuditChain(deployer_id="acme-health-prod", in_memory=True)
    e = chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um-agent",
        payload={"decision": "denied"},
    )
    # Tamper in place: flip the stored payload after the fact.
    object.__setattr__(e, "payload", {"decision": "approved"})
    assert chain.verify() is False
    with pytest.raises(AuditChainTamperError):
        chain.verify_strict()


def test_al_probe_03d_end_to_end_regeneration_detected_via_witness():
    """The hash chain alone cannot catch end-to-end regeneration; the external
    witness anchor is the control that makes it detectable. Production mode
    makes the witness non-optional."""
    witness = InMemoryWitness()
    chain = AuditChain(
        deployer_id="acme-health-prod",
        witness_register=witness,
        production=True,
        in_memory=True,
    )
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um-agent",
        payload={"decision": "approved"},
    )
    anchor_event = chain.anchor_to_witness()
    assert anchor_event is not None
    assert anchor_event.event_type == AuditEventType.WITNESS_ANCHOR
    assert len(witness.anchored) == 1
    # The published head is now witnessed; a regenerated chain would produce a
    # different head than the one the external witness recorded.
    assert witness.anchored[0].chain_head_hex != chain.chain_head()  # head advanced past the anchor


def test_al_probe_03e_production_refuses_without_witness():
    with pytest.raises(ValueError, match="requires a witness_register"):
        AuditChain(deployer_id="acme-health-prod", production=True, in_memory=True)


# --------------------------------------------------------------------------- #
# AL-PROBE-04 — P4 illegal one-call HALT/SHUTDOWN -> NORMAL -> refused          #
# --------------------------------------------------------------------------- #


def test_al_probe_04_halt_to_normal_one_call_refused():
    machine = DEFCONMachine(authorizer=AllowAuthorizer(), production=True)
    machine.manual_override(DEFCON.HALT, "ops-lead", "emergency stop")
    assert machine.level == DEFCON.HALT
    with pytest.raises(DEFCONOverrideRejectedError, match="transition-direction guard"):
        machine.manual_override(DEFCON.NORMAL, "ops-lead", "looks fine now")
    assert machine.level == DEFCON.HALT  # still halted


def test_al_probe_04b_shutdown_to_normal_one_call_refused():
    machine = DEFCONMachine(authorizer=AllowAuthorizer(), production=True)
    machine.manual_override(DEFCON.SHUTDOWN, "ops-lead", "kill")
    with pytest.raises(DEFCONOverrideRejectedError, match="transition-direction guard"):
        machine.manual_override(DEFCON.NORMAL, "ops-lead", "resume")


def test_al_probe_04c_stepwise_deescalation_allowed():
    machine = DEFCONMachine(authorizer=AllowAuthorizer(), production=True)
    machine.manual_override(DEFCON.HALT, "ops-lead", "stop")
    # One level down at a time is allowed.
    machine.manual_override(DEFCON.DANGER, "ops-lead", "step down 1")
    assert machine.level == DEFCON.DANGER
    machine.manual_override(DEFCON.ALERT, "ops-lead", "step down 2")
    assert machine.level == DEFCON.ALERT


def test_al_probe_04d_production_requires_authorizer():
    with pytest.raises(ValueError, match="requires an authorizer"):
        DEFCONMachine(production=True)


# --------------------------------------------------------------------------- #
# AL-PROBE-05 — P5 self-challenge (challenger == primary) -> rejected           #
# --------------------------------------------------------------------------- #


def _independence() -> IndependenceAttestation:
    return IndependenceAttestation(
        chosen_by="head-of-model-risk",
        chosen_at=datetime.now(UTC).isoformat(),
        not_same_owner=True,
        not_same_vendor_family=True,
        not_same_prompt_template=True,
        rationale="challenger is a different vendor reviewed by second line",
    )


def test_al_probe_05_self_challenge_rejected():
    """A model cannot challenge itself to a clean accept_primary."""
    model = lambda x: x  # noqa: E731

    with pytest.raises(ChallengerNotIndependentError, match="cannot challenge itself"):
        EffectiveChallengeHarness(
            primary_model=model,
            challenger_model=model,  # same object
            eval_set=[(1, 1), (2, 2)],
            independence=_independence(),
        )


def test_al_probe_05b_missing_independence_attestation_rejected():
    bad = IndependenceAttestation(
        chosen_by="head-of-model-risk",
        chosen_at=datetime.now(UTC).isoformat(),
        not_same_owner=True,
        not_same_vendor_family=False,  # incomplete
        not_same_prompt_template=True,
    )
    with pytest.raises(ChallengerNotIndependentError, match="attestation"):
        EffectiveChallengeHarness(
            primary_model=lambda x: x,
            challenger_model=lambda x: x + 1,
            eval_set=[(1, 1)],
            independence=bad,
        )


def test_al_probe_05c_independent_challenge_runs_and_records_attestation():
    chain = AuditChain(deployer_id="acme-health-prod", in_memory=True)
    harness = EffectiveChallengeHarness(
        primary_model=lambda x: x % 2,
        challenger_model=lambda x: (x + 1) % 2,  # disagrees on everything
        eval_set=[(0, 0), (1, 1), (2, 0), (3, 1)],
        independence=_independence(),
        audit_chain=chain,
        primary_id="vendor-a-model",
        challenger_id="vendor-b-model",
    )
    report = harness.run()
    assert report.disagreement_rate == 1.0
    assert report.recommendation == "escalate"
    # The independence attestation was written to the chain.
    last = chain._events[-1]
    assert last.event_type == AuditEventType.MODEL_VALIDATED
    att = last.payload["independence_attestation"]
    assert att["attested"] is True and att["code_detected"] is False
    assert att["chosen_by"] == "head-of-model-risk"

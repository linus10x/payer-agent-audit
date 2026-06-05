"""Unit + contract tests for the five primitives (non-probe paths).

Covers persistence, threshold algebra, attestation validity branches, and
schema roundtrip — the paths the AL-PROBES do not exercise.
"""

from __future__ import annotations

import json
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from payer_agent_audit.governance.audit_chain import (
    AuditChain,
    AuditChainTamperError,
    _compute_genesis_hash,
)
from payer_agent_audit.governance.autonomy_ladder import (
    ADVISORY,
    Attestation,
    PromotionEvidence,
    PromotionGateNotMet,
    check_a2_to_a3_promotion,
    required_oversight,
)
from payer_agent_audit.governance.defcon import (
    DEFCON,
    DEFCONMachine,
    DEFCONOverrideRejectedError,
    RiskMetrics,
)
from payer_agent_audit.governance.effective_challenge_harness import (
    EffectiveChallengeHarness,
    IndependenceAttestation,
)
from payer_agent_audit.governance.sovereign_veto import (
    InMemoryVetoStateStore,
    SovereignVeto,
    VetoReason,
)
from payer_agent_audit.schemas.audit_event import (
    AuditEvent,
    AuditEventType,
    AutonomyLevel,
)


def _allow():
    class _A:
        def authorize(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
            return True

    return _A()


# --------------------------------------------------------------------------- #
# Schema — AuditEvent                                                          #
# --------------------------------------------------------------------------- #


def test_audit_event_create_and_roundtrip():
    e = AuditEvent.create(
        event_type=AuditEventType.DECISION_MADE,
        autonomy_level=AutonomyLevel.A2,
        agent_id="a",
        payload={"k": "v"},
        prev_hash="0" * 64,
        event_id="fixed-id",
        timestamp="2026-06-05T00:00:00+00:00",
        actor_id="op",
    )
    d = e.to_dict()
    assert d["event_id"] == "fixed-id"
    e2 = AuditEvent.from_jsonl(d)
    assert e2.event_hash == e.event_hash
    assert json.loads(e.to_jsonl())["agent_id"] == "a"


def test_audit_event_from_jsonl_detects_tamper():
    e = AuditEvent.create(
        event_type=AuditEventType.DECISION_MADE,
        autonomy_level=AutonomyLevel.A2,
        agent_id="a",
        payload={"k": "v"},
        prev_hash="0" * 64,
    )
    d = e.to_dict()
    d["payload"] = {"k": "TAMPERED"}
    with pytest.raises(AuditChainTamperError, match="event_hash mismatch"):
        AuditEvent.from_jsonl(d)


# --------------------------------------------------------------------------- #
# P3 — AuditChain persistence + genesis                                        #
# --------------------------------------------------------------------------- #


def test_chain_jsonl_persistence_and_reload(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    chain = AuditChain(log_file=log, deployer_id="acme-health-prod")
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um",
        payload={"d": "approved"},
    )
    assert log.exists()
    # Reload from disk — genesis preserved, verifies True.
    reloaded = AuditChain(log_file=log, deployer_id="acme-health-prod")
    assert reloaded.verify() is True
    assert len(reloaded) == len(chain)


def test_chain_legacy_reload_emits_deprecation(tmp_path: Path):
    log = tmp_path / "legacy.jsonl"
    chain = AuditChain(log_file=log)  # legacy, no deployer_id
    chain.append(
        event_type=AuditEventType.COVERAGE_DETERMINATION,
        autonomy_level=AutonomyLevel.A1,
        agent_id="cov",
        payload={"d": "covered"},
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        AuditChain(log_file=log)
    assert any(issubclass(x.category, DeprecationWarning) for x in w)


def test_chain_tamper_on_disk_detected(tmp_path: Path):
    log = tmp_path / "t.jsonl"
    chain = AuditChain(log_file=log, deployer_id="acme-health-prod")
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um",
        payload={"d": "denied"},
    )
    lines = log.read_text().splitlines()
    rec = json.loads(lines[-1])
    rec["payload"] = {"d": "approved"}
    lines[-1] = json.dumps(rec, sort_keys=True)
    log.write_text("\n".join(lines) + "\n")
    with pytest.raises(AuditChainTamperError):
        AuditChain(log_file=log, deployer_id="acme-health-prod")


def test_chain_empty_head_is_genesis_sentinel():
    chain = AuditChain(in_memory=True)
    assert chain.chain_head() == "0" * 64


def test_chain_anchor_returns_none_without_witness():
    chain = AuditChain(in_memory=True, deployer_id="x")
    assert chain.anchor_to_witness() is None


def test_compute_genesis_hash_is_deployer_keyed():
    a = _compute_genesis_hash("acme", "2026-01-01T00:00:00+00:00")
    b = _compute_genesis_hash("beta", "2026-01-01T00:00:00+00:00")
    assert a != b
    assert len(a) == 64


def test_chain_deterministic_genesis_across_hosts():
    iso = "2026-01-01T00:00:00+00:00"
    c1 = AuditChain(in_memory=True, deployer_id="acme", chain_creation_iso=iso)
    c2 = AuditChain(in_memory=True, deployer_id="acme", chain_creation_iso=iso)
    assert c1._events[0].event_hash == c2._events[0].event_hash


# --------------------------------------------------------------------------- #
# P1 — autonomy ladder attestation validity branches                          #
# --------------------------------------------------------------------------- #


def test_attestation_empty_attester_rejected():
    a = Attestation("c", "", datetime.now(UTC).isoformat(), "ref")
    ok, reason = a.is_valid(agent_id="agent")
    assert not ok and "empty" in reason


def test_attestation_missing_evidence_rejected():
    a = Attestation("c", "mrm", datetime.now(UTC).isoformat(), "")
    ok, reason = a.is_valid(agent_id="agent")
    assert not ok and "evidence" in reason


def test_attestation_false_value_rejected():
    a = Attestation("c", "mrm", datetime.now(UTC).isoformat(), "ref", value=False)
    ok, reason = a.is_valid(agent_id="agent")
    assert not ok and "False" in reason


def test_attestation_bad_timestamp_rejected():
    a = Attestation("c", "mrm", "not-a-date", "ref")
    ok, reason = a.is_valid(agent_id="agent")
    assert not ok and "ISO-8601" in reason


def test_attestation_stale_rejected():
    old = (datetime.now(UTC) - timedelta(days=365)).isoformat()
    a = Attestation("c", "mrm", old, "ref")
    ok, reason = a.is_valid(agent_id="agent")
    assert not ok and "stale" in reason


def test_attestation_future_rejected():
    future = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    a = Attestation("c", "mrm", future, "ref")
    ok, reason = a.is_valid(agent_id="agent")
    assert not ok and "future" in reason


def test_attestation_naive_timestamp_accepted_as_utc():
    naive = datetime.now().replace(tzinfo=None).isoformat()
    a = Attestation("c", "mrm", naive, "ref")
    ok, _ = a.is_valid(agent_id="agent")
    assert ok


def test_promotion_gate_raise_if_blocked():
    bad = Attestation("c", "agent", datetime.now(UTC).isoformat(), "ref")  # self
    ev = PromotionEvidence(
        sovereign_veto_load_tested=bad,
        audit_ledger_running_for=timedelta(days=120),
        audit_ledger_running_attestation=Attestation(
            "l", "mrm", datetime.now(UTC).isoformat(), "ref"
        ),
        shadow_mode_running_for=timedelta(days=45),
        shadow_mode_attestation=Attestation("s", "mrm", datetime.now(UTC).isoformat(), "ref"),
        circuit_breaker_test_recent=Attestation("cb", "mrm", datetime.now(UTC).isoformat(), "ref"),
    )
    report = check_a2_to_a3_promotion(ev, agent_id="agent")
    with pytest.raises(PromotionGateNotMet):
        report.raise_if_blocked()
    assert report.advisory is ADVISORY


def test_required_oversight_all_levels():
    for lvl in AutonomyLevel:
        assert isinstance(required_oversight(lvl), str)


# --------------------------------------------------------------------------- #
# P4 — DEFCON threshold algebra + paths                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "metrics,expected",
    [
        (RiskMetrics(breach_rate=0.0), DEFCON.NORMAL),
        (RiskMetrics(breach_rate=0.06), DEFCON.CAUTION),
        (RiskMetrics(breach_rate=0.12), DEFCON.ALERT),
        (RiskMetrics(consecutive_failures=4), DEFCON.ALERT),
        (RiskMetrics(breach_rate=0.22), DEFCON.DANGER),
        (RiskMetrics(anomaly_score=0.86), DEFCON.DANGER),
        (RiskMetrics(consecutive_failures=6), DEFCON.DANGER),
        (RiskMetrics(breach_rate=0.31), DEFCON.HALT),
        (RiskMetrics(anomaly_score=0.96), DEFCON.HALT),
        (RiskMetrics(breach_rate=0.41), DEFCON.SHUTDOWN),
    ],
)
def test_defcon_compute_target(metrics, expected):
    m = DEFCONMachine(authorizer=_allow(), production=True)
    assert m.evaluate(metrics) == expected


def test_defcon_evaluate_never_auto_deescalates():
    m = DEFCONMachine(authorizer=_allow(), production=True)
    m.evaluate(RiskMetrics(breach_rate=0.31))  # HALT
    assert m.level == DEFCON.HALT
    # Metrics calm down — machine stays halted (no auto de-escalation).
    m.evaluate(RiskMetrics(breach_rate=0.0))
    assert m.level == DEFCON.HALT


def test_defcon_manual_escalation_allowed_single_call():
    m = DEFCONMachine(authorizer=_allow(), production=True)
    m.manual_override(DEFCON.DANGER, "op", "escalate")
    assert m.level == DEFCON.DANGER


def test_defcon_deescalation_skip_more_than_one_rejected():
    m = DEFCONMachine(authorizer=_allow(), production=True)
    m.manual_override(DEFCON.DANGER, "op", "set")
    with pytest.raises(DEFCONOverrideRejectedError, match="one level per call"):
        m.manual_override(DEFCON.NORMAL, "op", "jump")


def test_defcon_override_same_level_noop():
    m = DEFCONMachine(authorizer=_allow(), production=True)
    assert m.manual_override(DEFCON.NORMAL, "op", "noop") == DEFCON.NORMAL


def test_defcon_unauthorized_operator_rejected():
    class Deny:
        def authorize(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
            return False

    m = DEFCONMachine(authorizer=Deny(), production=True)
    with pytest.raises(DEFCONOverrideRejectedError, match="not authorized"):
        m.manual_override(DEFCON.HALT, "rogue", "stop")


def test_defcon_advisory_warns_without_authorizer():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        DEFCONMachine()
    assert any("advisory mode" in str(x.message) for x in w)


def test_defcon_history_recorded():
    m = DEFCONMachine(authorizer=_allow(), production=True)
    m.evaluate(RiskMetrics(breach_rate=0.12))
    assert len(m.history()) == 1
    assert m.history()[0]["to"] == "ALERT"


# --------------------------------------------------------------------------- #
# P2 — sovereign veto extra paths                                             #
# --------------------------------------------------------------------------- #


def test_veto_advisory_warns_without_authorizer():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        SovereignVeto("agent")
    assert any("advisory mode" in str(x.message) for x in w)


def test_veto_callbacks_and_history():
    fired = {"veto": 0, "clear": 0}
    v = SovereignVeto(
        "agent",
        on_veto=lambda r: fired.__setitem__("veto", fired["veto"] + 1),
        on_clear=lambda r: fired.__setitem__("clear", fired["clear"] + 1),
        authorizer=_allow(),
        production=True,
    )
    rec = v.trigger(VetoReason.RISK_LIMIT_BREACH, "op", "desc")
    assert fired["veto"] == 1
    assert len(v.active_vetos()) == 1
    v.clear(operator_id="op-2", reason="ok", veto_id=rec.veto_id)
    assert fired["clear"] == 1
    assert len(v.history()) == 1
    assert v.allow_execution()


def test_veto_state_store_persistence_roundtrip():
    store = InMemoryVetoStateStore()
    v1 = SovereignVeto("agent", authorizer=_allow(), production=True, state_store=store)
    v1.trigger(VetoReason.ANOMALY_DETECTED, "op", "d")
    # New instance loads prior state from the store.
    v2 = SovereignVeto("agent", authorizer=_allow(), production=True, state_store=store)
    assert v2.is_vetoed
    assert len(v2.history()) == 1


def test_veto_record_to_dict():
    v = SovereignVeto("agent", authorizer=_allow(), production=True)
    rec = v.trigger(VetoReason.COMPLIANCE_FLAG, "op", "d")
    d = rec.to_dict()
    assert d["reason"] == "compliance_flag"
    assert d["cleared_by"] is None


# --------------------------------------------------------------------------- #
# P5 — effective challenge extra paths                                        #
# --------------------------------------------------------------------------- #


def _ind() -> IndependenceAttestation:
    return IndependenceAttestation(
        chosen_by="mrm",
        chosen_at=datetime.now(UTC).isoformat(),
        not_same_owner=True,
        not_same_vendor_family=True,
        not_same_prompt_template=True,
    )


def test_challenge_empty_eval_set_raises():
    h = EffectiveChallengeHarness(
        primary_model=lambda x: x,
        challenger_model=lambda x: x + 1,
        eval_set=[],
        independence=_ind(),
    )
    with pytest.raises(ValueError, match="empty"):
        h.run()


def test_challenge_investigate_band():
    # 1 disagreement in 10 -> 0.10 -> investigate band (0.05 < r <= 0.30).
    eval_set = [(i, 0) for i in range(10)]
    primary = lambda x: 0  # noqa: E731
    challenger = lambda x: 1 if x == 9 else 0  # noqa: E731
    h = EffectiveChallengeHarness(
        primary_model=primary,
        challenger_model=challenger,
        eval_set=eval_set,
        independence=_ind(),
    )
    report = h.run()
    assert report.recommendation == "investigate"


def test_challenge_accept_band_requires_real_independence():
    # Near-identical but DISTINCT models agreeing -> accept_primary is allowed
    # ONLY because they are genuinely independent objects + attested.
    eval_set = [(i, i % 2) for i in range(20)]
    h = EffectiveChallengeHarness(
        primary_model=lambda x: x % 2,
        challenger_model=lambda x: x % 2 if x != 0 else x % 2,
        eval_set=eval_set,
        independence=_ind(),
        primary_id="vendor-a",
        challenger_id="vendor-b",
    )
    report = h.run()
    assert report.recommendation == "accept_primary"
    assert report.disagreement_rate == 0.0


def test_challenge_same_id_rejected():
    from payer_agent_audit.governance.effective_challenge_harness import (
        ChallengerNotIndependentError,
    )

    with pytest.raises(ChallengerNotIndependentError, match="distinct"):
        EffectiveChallengeHarness(
            primary_model=lambda x: x,
            challenger_model=lambda x: x + 1,
            eval_set=[(1, 1)],
            independence=_ind(),
            primary_id="same",
            challenger_id="same",
        )


def test_independence_bad_timestamp_rejected():
    from payer_agent_audit.governance.effective_challenge_harness import (
        ChallengerNotIndependentError,
    )

    bad = IndependenceAttestation(
        chosen_by="mrm",
        chosen_at="not-a-date",
        not_same_owner=True,
        not_same_vendor_family=True,
        not_same_prompt_template=True,
    )
    with pytest.raises(ChallengerNotIndependentError, match="ISO-8601"):
        EffectiveChallengeHarness(
            primary_model=lambda x: x,
            challenger_model=lambda x: x + 1,
            eval_set=[(1, 1)],
            independence=bad,
        )


# --------------------------------------------------------------------------- #
# Mutation-hardening tests (kill the survivors from scripts/mutation_check.py)  #
# --------------------------------------------------------------------------- #


def test_defcon_evaluate_no_transition_when_target_equals_level():
    """target == current must NOT record a transition (kills `> -> >=`)."""
    m = DEFCONMachine(authorizer=_allow(), production=True)
    m.evaluate(RiskMetrics(breach_rate=0.0))  # NORMAL -> NORMAL
    assert m.level == DEFCON.NORMAL
    assert m.history() == []


def test_defcon_two_level_deescalation_rejected_one_level_message():
    """ALERT -> NORMAL is a 2-level drop -> rejected with the step message
    (kills `(current - target) > 1` -> `> 2`)."""
    m = DEFCONMachine(authorizer=_allow(), production=True)
    m.manual_override(DEFCON.ALERT, "op", "set")
    with pytest.raises(DEFCONOverrideRejectedError, match="one level per call"):
        m.manual_override(DEFCON.NORMAL, "op", "jump")
    assert m.level == DEFCON.ALERT


def test_defcon_halt_to_normal_uses_hard_stop_message():
    """HALT -> NORMAL must raise the HARD-STOP-specific message (kills removing
    HALT from _HARD_STOP_STATES, which would fall through to the generic
    step-guard message instead)."""
    m = DEFCONMachine(authorizer=_allow(), production=True)
    m.manual_override(DEFCON.HALT, "op", "stop")
    with pytest.raises(DEFCONOverrideRejectedError, match="Recovery from a hard stop"):
        m.manual_override(DEFCON.NORMAL, "op", "resume")


def test_promotion_gate_boundary_exactly_minimum_tenure_passes():
    """Exactly 90 days ledger + 30 days shadow PASSES (kills `< days` -> `<= days`)."""
    ev = PromotionEvidence(
        sovereign_veto_load_tested=Attestation("veto", "mrm", datetime.now(UTC).isoformat(), "ref"),
        audit_ledger_running_for=timedelta(days=90),  # exactly the floor
        audit_ledger_running_attestation=Attestation(
            "l", "mrm", datetime.now(UTC).isoformat(), "ref"
        ),
        shadow_mode_running_for=timedelta(days=30),  # exactly the floor
        shadow_mode_attestation=Attestation("s", "mrm", datetime.now(UTC).isoformat(), "ref"),
        circuit_breaker_test_recent=Attestation("cb", "mrm", datetime.now(UTC).isoformat(), "ref"),
    )
    report = check_a2_to_a3_promotion(ev, agent_id="agent")
    assert report.passed is True


def test_promotion_gate_one_day_under_minimum_fails():
    """89 days ledger fails — confirms the boundary is real, not loosened."""
    ev = PromotionEvidence(
        sovereign_veto_load_tested=Attestation("veto", "mrm", datetime.now(UTC).isoformat(), "ref"),
        audit_ledger_running_for=timedelta(days=89),
        audit_ledger_running_attestation=Attestation(
            "l", "mrm", datetime.now(UTC).isoformat(), "ref"
        ),
        shadow_mode_running_for=timedelta(days=30),
        shadow_mode_attestation=Attestation("s", "mrm", datetime.now(UTC).isoformat(), "ref"),
        circuit_breaker_test_recent=Attestation("cb", "mrm", datetime.now(UTC).isoformat(), "ref"),
    )
    report = check_a2_to_a3_promotion(ev, agent_id="agent")
    assert report.passed is False

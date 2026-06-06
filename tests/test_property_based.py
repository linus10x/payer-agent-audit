"""Property-based tests (volume tier) — thousands of cases per primitive.

Uses ``hypothesis`` to generate the hard cases the happy path misses. The
volume target is thousands of generated examples per primitive across the
run. Marked ``slow`` so fast local iteration can skip via ``-m 'not slow'``.

Invariants asserted:
  P3 ledger     — append-then-verify always True; any single in-place mutation
                  is detected; both hardened + legacy chains verify.
  P1 level-gate — monotonicity: insufficient tenure never passes; a passing
                  record never flips to fail by ADDING tenure.
  P2 veto       — un-self-clearability for any agent/operator strings.
  P4 DEFCON     — transition-direction algebra: HALT/SHUTDOWN->NORMAL one-call
                  always refused; escalation always allowed.
  P5 challenge  — identical-callable challenger always rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from payer_agent_audit.governance.audit_chain import AuditChain
from payer_agent_audit.governance.autonomy_ladder import (
    Attestation,
    PromotionEvidence,
    check_a2_to_a3_promotion,
)
from payer_agent_audit.governance.defcon import (
    DEFCON,
    DEFCONMachine,
    DEFCONOverrideRejectedError,
)
from payer_agent_audit.governance.effective_challenge_harness import (
    ChallengerNotIndependentError,
    EffectiveChallengeHarness,
    IndependenceAttestation,
)
from payer_agent_audit.governance.sovereign_veto import (
    SovereignVeto,
    VetoBlockedError,
    VetoReason,
)
from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

pytestmark = pytest.mark.slow

_SETTINGS = settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])


def _allow():
    class _A:
        def authorize(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
            return True

    return _A()


# --------------------------------------------------------------------------- #
# P3 ledger invariants                                                        #
# --------------------------------------------------------------------------- #

_payloads = st.lists(
    st.dictionaries(
        st.text(min_size=1, max_size=8),
        st.one_of(st.integers(), st.text(max_size=12), st.booleans()),
        max_size=4,
    ),
    min_size=1,
    max_size=12,
)


@_SETTINGS
@given(payloads=_payloads, hardened=st.booleans())
def test_prop_chain_appends_verify(payloads, hardened):
    chain = AuditChain(
        in_memory=True,
        deployer_id="acme-health-prod" if hardened else None,
    )
    for p in payloads:
        chain.append(
            event_type=AuditEventType.PRIOR_AUTH_DECISION,
            autonomy_level=AutonomyLevel.A2,
            agent_id="um",
            payload=p,
        )
    assert chain.verify() is True
    chain.verify_strict()


@_SETTINGS
@given(payloads=_payloads, idx=st.integers(min_value=0, max_value=20))
def test_prop_chain_in_place_tamper_detected(payloads, idx):
    chain = AuditChain(in_memory=True, deployer_id="acme-health-prod")
    for p in payloads:
        chain.append(
            event_type=AuditEventType.COVERAGE_DETERMINATION,
            autonomy_level=AutonomyLevel.A1,
            agent_id="cov",
            payload=p,
        )
    target = idx % len(chain._events)
    # Skip the deployer genesis event (index 0) — mutate a real event.
    if target == 0:
        target = min(1, len(chain._events) - 1)
    victim = chain._events[target]
    object.__setattr__(victim, "payload", {"__tampered__": True})
    if len(chain._events) > 1 or target != 0:
        assert chain.verify() is False


# --------------------------------------------------------------------------- #
# P1 level-gate monotonicity                                                   #
# --------------------------------------------------------------------------- #


def _att(attester: str = "mrm") -> Attestation:
    return Attestation("c", attester, datetime.now(UTC).isoformat(), "ref")


@_SETTINGS
@given(
    ledger_days=st.integers(min_value=0, max_value=400),
    shadow_days=st.integers(min_value=0, max_value=200),
)
def test_prop_level_gate_tenure_monotonic(ledger_days, shadow_days):
    ev = PromotionEvidence(
        sovereign_veto_load_tested=_att(),
        audit_ledger_running_for=timedelta(days=ledger_days),
        audit_ledger_running_attestation=_att(),
        shadow_mode_running_for=timedelta(days=shadow_days),
        shadow_mode_attestation=_att(),
        circuit_breaker_test_recent=_att(),
    )
    report = check_a2_to_a3_promotion(ev, agent_id="agent")
    expected_pass = ledger_days >= 90 and shadow_days >= 30
    assert report.passed is expected_pass


@_SETTINGS
@given(
    agent=st.text(min_size=1, max_size=16).filter(lambda s: s.strip() != ""),
    pad=st.sampled_from(["", " ", "  ", "\t"]),
    upper=st.booleans(),
)
def test_prop_level_gate_rejects_self_attestation(agent, pad, upper):
    # A whitespace/case VARIANT of the agent id must still be caught as
    # self-attestation — not just the exact string (the normalization guard).
    attester = f"{pad}{agent.upper() if upper else agent}{pad}"
    ev = PromotionEvidence(
        sovereign_veto_load_tested=_att(attester=attester),
        audit_ledger_running_for=timedelta(days=120),
        audit_ledger_running_attestation=_att(attester=attester),
        shadow_mode_running_for=timedelta(days=45),
        shadow_mode_attestation=_att(attester=attester),
        circuit_breaker_test_recent=_att(attester=attester),
    )
    report = check_a2_to_a3_promotion(ev, agent_id=agent)
    assert report.passed is False


# --------------------------------------------------------------------------- #
# P2 veto un-self-clearability                                                 #
# --------------------------------------------------------------------------- #


@_SETTINGS
@given(agent_id=st.text(min_size=1, max_size=24))
def test_prop_veto_un_self_clearable(agent_id):
    v = SovereignVeto(agent_id, authorizer=_allow(), production=True)
    v.trigger(VetoReason.MANUAL_OPERATOR, "op", "d")
    with pytest.raises(VetoBlockedError):
        v.clear(operator_id=agent_id, reason="self")
    assert v.is_vetoed


# --------------------------------------------------------------------------- #
# P4 DEFCON transition-direction algebra                                       #
# --------------------------------------------------------------------------- #

_states = st.sampled_from(list(DEFCON))


@_SETTINGS
@given(start=_states, target=_states)
def test_prop_defcon_direction_algebra(start, target):
    m = DEFCONMachine(authorizer=_allow(), production=True)
    # Drive to the start state via single-step escalation from NORMAL.
    if start > DEFCON.NORMAL:
        for lvl in range(DEFCON.NORMAL + 1, start + 1):
            m.manual_override(DEFCON(lvl), "op", "up")
    assert m.level == start

    if target >= start:
        # Escalation (or noop) always succeeds in one call.
        m.manual_override(target, "op", "go")
        assert m.level == target
    else:
        step = start - target
        from_hard_stop_to_normal = (
            start in (DEFCON.HALT, DEFCON.SHUTDOWN) and target == DEFCON.NORMAL
        )
        if step > 1 or from_hard_stop_to_normal:
            with pytest.raises(DEFCONOverrideRejectedError):
                m.manual_override(target, "op", "down")
            assert m.level == start
        else:
            m.manual_override(target, "op", "down")
            assert m.level == target


# --------------------------------------------------------------------------- #
# P5 self-challenge rejection                                                  #
# --------------------------------------------------------------------------- #


@_SETTINGS
@given(n=st.integers(min_value=1, max_value=20))
def test_prop_self_challenge_always_rejected(n):
    model = lambda x: x  # noqa: E731
    ind = IndependenceAttestation(
        chosen_by="mrm",
        chosen_at=datetime.now(UTC).isoformat(),
        not_same_owner=True,
        not_same_vendor_family=True,
        not_same_prompt_template=True,
    )
    with pytest.raises(ChallengerNotIndependentError):
        EffectiveChallengeHarness(
            primary_model=model,
            challenger_model=model,
            eval_set=[(i, i) for i in range(n)],
            independence=ind,
        )

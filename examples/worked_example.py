"""Worked example — the out-of-envelope case, end to end.

A health plan stands up an AI agent to help clear its prior-authorization
queue. The decision class is UM prior auth on a Medicare Advantage plan,
where CMS-0057-F sets a 72-hour clock for an expedited/urgent request.

This script walks the path the README promises:

  1. The decision class — a Medicare Advantage expedited prior-auth request.
  2. The agent acts — it reaches a determination.
  3. The envelope catches the out-of-envelope case — the determination
     landed at 80 hours, past the 72-hour regulatory floor. The control
     does NOT decide whether the care was medically necessary; it decides
     whether the decision was TIMELY under the rule that governs this plan.
  4. The audit entry — the breach is written to the hash-chain ledger that
     detects tampering within its trust boundary, so the record exists
     whether or not anyone is watching.
  5. The demotion — the operational-risk signal escalates the agent's
     autonomy state (DEFCON) and a sovereign veto engages, so the agent
     stops making this class of decision until a human re-authorizes it.

It governs the RECORD of the decision, not the medical-necessity
determination. The clinician's judgment belongs to the clinician.

Run: python3 examples/worked_example.py
"""

from __future__ import annotations

import warnings
from datetime import UTC, datetime, timedelta

from payer_agent_audit.governance import (
    DEFCON,
    AuditChain,
    DEFCONMachine,
    RiskMetrics,
    SovereignVeto,
    VetoReason,
)
from payer_agent_audit.payer import (
    ClinicianOfRecord,
    ClinicianOfRecordControl,
    FundingType,
    RequestCategory,
    UMTimelinessControl,
)


def run() -> AuditChain:
    """Govern one out-of-envelope Medicare Advantage prior-auth decision."""
    print("=" * 70)
    print("payer-agent-audit — worked example: the breach, end to end")
    print("=" * 70)

    # The ledger is the record of governance. Hardened genesis (deployer-keyed)
    # so event #0 is bound to this deployer. In production you would also wire
    # an external witness anchor — see ARCHITECTURE.md / the trust boundary.
    chain = AuditChain(deployer_id="acme-health-prod", in_memory=True)

    # ---- 1 + 2. The decision class, and the agent acting on it. -----------
    # Medicare Advantage, expedited/urgent prior auth: CMS-0057-F 72h clock.
    received = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    decided = received + timedelta(hours=80)  # the agent decided at hour 80
    print("\n[1-2] Decision class: Medicare Advantage expedited prior auth (PA-12345)")
    print(f"      received {received.isoformat()}  ->  decided {decided.isoformat()}")

    # ---- 3. The envelope catches the out-of-envelope case. ----------------
    # A medical-necessity denial still requires an attested clinician of
    # record — the control refuses to let an agent issue that denial alone.
    # (This is presence/attestation, NOT a medical-necessity determination.)
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

    # The timeliness control measures the decision against the rule the
    # plan's funding type imposes. 80h > 72h -> BREACHED.
    result = UMTimelinessControl(chain).check(
        funding_type=FundingType.MEDICARE_ADVANTAGE,
        category=RequestCategory.EXPEDITED_URGENT,
        request_received_at=received,
        decision_made_at=decided,
        case_ref="PA-12345",
    )
    print("\n[3] UM-timeliness envelope:")
    print(f"      deadline   = {result.deadline}  ({result.citation})")
    print(f"      elapsed    = {result.elapsed}")
    print(f"      met        = {result.met}   <-- out of envelope (80h > 72h)")
    assert result.met is False  # the breach is real, not the happy path

    # ---- 4. The audit entry. ----------------------------------------------
    # Every check above already wrote to the chain. Prove the chain is
    # internally consistent (detects in-place tampering within its boundary).
    print("\n[4] Audit ledger:")
    print(f"      events recorded = {len(chain)}")
    print(f"      chain verifies  = {chain.verify()}")
    print(f"      chain head      = {chain.chain_head()[:16]}...")
    assert chain.verify()

    # ---- 5. The demotion. -------------------------------------------------
    # The breach is an operational-risk signal. It escalates the agent's
    # DEFCON autonomy state, and a sovereign veto engages so the agent
    # cannot keep issuing this decision class until a human re-authorizes.
    # (DEFCON metrics are operational risk — denial/breach rates — NOT a
    # clinical determination.)
    # Advisory mode for the demo: in production you pass production=True + an
    # Authorizer. The advisory-mode warning is expected here, so we mute it.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        defcon = DEFCONMachine(audit_chain=chain)
        veto = SovereignVeto(agent_id="um-prior-auth-agent")
    new_state = defcon.evaluate(RiskMetrics(breach_rate=0.35))  # >= HALT threshold
    print("\n[5] Demotion:")
    print(f"      DEFCON state   = {new_state.name}")
    assert new_state >= DEFCON.HALT

    veto.trigger(
        reason=VetoReason.UM_TIMELINESS_AT_RISK,
        triggered_by="compliance-monitor",
        description="PA-12345 decided at 80h vs the 72h CMS-0057-F floor",
    )
    print(f"      veto engaged   = {veto.is_vetoed}")
    print(f"      agent may run  = {veto.allow_execution()}   <-- halted pending human re-auth")
    assert veto.is_vetoed is True
    assert veto.allow_execution() is False

    print("\n" + "-" * 70)
    print("It governed the RECORD — timeliness, clinician presence, and the")
    print("demotion that followed the breach. It made NO medical-necessity or")
    print("clinical determination. That judgment stays with the clinician.")
    print("-" * 70)
    return chain


if __name__ == "__main__":
    c = run()
    print(f"\nfinal: chain verified={c.verify()}, {len(c)} events.")

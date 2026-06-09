# The Autonomy Ladder in this library

`payer-agent-audit` is one of six co-equal regulated-vertical reference libraries implementing the **Autonomy Ladder** — a governance framework for autonomous AI in regulated operations. The framework, the whitepaper, and the cross-vertical family live at **[autonomy-ladder.io](https://autonomy-ladder.io)**; the family index is the meta-repo **[autonomy-ladder-libraries](https://github.com/linus10x/autonomy-ladder-libraries)**.

This file maps the primitives and controls *in this repository* to the ladder.

## The ladder — A0 to A4

The Autonomy Ladder classifies an agent's **write authority**, not its intelligence. Every rung is **demotable**: an agent that breaches its envelope drops back down, and the drop is recorded.

| Level | Authority | Human oversight |
|---|---|---|
| **A0** | Read-only / informational | Agent recommends; no write authority |
| **A1** | Assisted | Human approves every write |
| **A2** | Delegated | Agent writes inside a hard envelope; sampled review |
| **A3** | Supervised autonomous | Sovereign veto + live audit ledger required |
| **A4** | Production autonomous | A3 plus operator-validated escalation |

The oversight text above is the advisory string this library returns from `required_oversight(level)` in `governance/autonomy_ladder.py`.

## How each primitive maps to the ladder

The five domain-agnostic primitives are the rungs and the rails between them. The three health-payer controls sit on top of the primitives and encode the UM / prior-auth / appeals decision class.

| Primitive / control | Module | Ladder role |
|---|---|---|
| **Autonomy-ladder level-gate** | `governance/autonomy_ladder.py` | The gate between rungs. Refuses A2→A3 promotion until lower-level controls are met and **independently attested** (rejects self-attestation, stale, or evidence-less claims). Advisory by design and labeled so. |
| **Sovereign veto** | `governance/sovereign_veto.py` | The non-overridable stop at A3/A4. A human kill switch the agent **cannot clear for itself**; engaging it demotes the agent out of autonomous operation until a human re-authorizes. |
| **Hash-chain audit ledger** | `governance/audit_chain.py` | The live record A3 requires. A hash-chain ledger that detects tampering within its trust boundary; production mode is fail-closed without an **external witness anchor**. |
| **DEFCON state machine** | `governance/defcon.py` | The demotion mechanism. Escalation is immediate; de-escalation is stepwise and re-authorized — a one-call `HALT`/`SHUTDOWN → NORMAL` is forbidden. This is how a breach mechanically lowers the rung. |
| **Witness anchor** | `governance/witness_anchor.py` | Converts the internally-consistent ledger into an adversarially detectable one by anchoring the chain head out-of-band (OpenTimestamps / Rekor / a regulator log). Non-optional in production mode. |
| **Effective-challenge harness** | `governance/effective_challenge_harness.py` | The independent-review rail under promotion. Enforces challenger ≠ primary; records an operator independence attestation to the ledger. |
| **UM timeliness** | `payer/um_timeliness.py` | The A2 hard envelope for the decision class — the regulatory clock (CMS-0057-F / ERISA / state DOI) the agent's decision must land inside. |
| **Clinician of record** | `payer/clinician_of_record.py` | The A2 envelope on medical-judgment denials — refuses an autonomous denial without an attested, licensed clinician. |
| **Appeal / IRO pathway** | `payer/appeal_iro.py` | The A2 process-rights envelope — internal appeal + IRO routing, with ERISA full-and-fair-review reviewer independence. |
| **Funding type** | `payer/funding_type.py` | The obligation router — maps each decision to the regime its funding type imposes, so the envelope above is the *correct* envelope for this plan. |

## The decision class is a parameter

The five primitives are domain-agnostic; the ladder structure (A0→A4, every rung demotable) lifts into any regulated decision class without inheriting another vertical's assumptions. This repo encodes the class as **health-insurance payer — utilization management, prior authorization, appeals**. The sibling libraries encode the same primitives for their own classes:

- [`finserv-agent-audit`](https://github.com/linus10x/finserv-agent-audit) — cross-vertical financial services
- [`banking-agent-audit`](https://github.com/linus10x/banking-agent-audit) — banking (model risk · ECOA/Reg B · BSA/AML/OFAC)
- [`payments-agent-audit`](https://github.com/linus10x/payments-agent-audit) — payments (OFAC · Reg E · rail finality)
- [`private-capital-agent-audit`](https://github.com/linus10x/private-capital-agent-audit) — SEC-registered investment advisers (Advisers Act §206)
- [`cre-agent-audit`](https://github.com/linus10x/cre-agent-audit) — commercial real estate

See the worked path through one rung and one demotion in [`WORKED_EXAMPLE.md`](WORKED_EXAMPLE.md), and the framework itself at [autonomy-ladder.io](https://autonomy-ladder.io).
